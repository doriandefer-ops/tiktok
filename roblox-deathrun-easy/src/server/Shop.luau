-- Boutique côté serveur (ModuleScript dans ServerScriptService)
-- Tous les achats sont validés ici : le client ne fait qu'ouvrir la fenêtre d'achat Roblox.
local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local StarterPlayer = game:GetService("StarterPlayer")

local Config = require(ReplicatedStorage:WaitForChild("DeathrunShared"):WaitForChild("Config"))

local MAX_RECEIPTS = 50

local Shop = {}

local api = nil -- fonctions fournies par Main (sessions, sauvegarde, progression)
local productsById = {} -- [productId] = produit
local passKeyById = {} -- [gamePassId] = "Speed" / "Trail"

for _, product in Config.PRODUCTS do
	if product.id ~= 0 then
		productsById[product.id] = product
	end
end
for key, pass in Config.GAMEPASSES do
	if pass.id ~= 0 then
		passKeyById[pass.id] = key
	end
end

---------------------------------------------------------------------------
-- Avantages des Game Pass
---------------------------------------------------------------------------
local function setTrail(root, enabled)
	local existing = root:FindFirstChild("DR_Trail")
	if enabled and not existing then
		local top = Instance.new("Attachment")
		top.Name = "DR_TrailTop"
		top.Position = Vector3.new(0, 0.8, 0)
		top.Parent = root
		local bottom = Instance.new("Attachment")
		bottom.Name = "DR_TrailBottom"
		bottom.Position = Vector3.new(0, -0.8, 0)
		bottom.Parent = root

		local trail = Instance.new("Trail")
		trail.Name = "DR_Trail"
		trail.Attachment0 = top
		trail.Attachment1 = bottom
		trail.Lifetime = 0.6
		trail.LightEmission = 0.6
		trail.Transparency = NumberSequence.new(0.1, 1)
		trail.Color = ColorSequence.new({
			ColorSequenceKeypoint.new(0, Color3.fromRGB(255, 60, 60)),
			ColorSequenceKeypoint.new(0.2, Color3.fromRGB(255, 170, 40)),
			ColorSequenceKeypoint.new(0.4, Color3.fromRGB(255, 240, 60)),
			ColorSequenceKeypoint.new(0.6, Color3.fromRGB(60, 230, 90)),
			ColorSequenceKeypoint.new(0.8, Color3.fromRGB(60, 140, 255)),
			ColorSequenceKeypoint.new(1, Color3.fromRGB(190, 80, 255)),
		})
		trail.Parent = root
	elseif not enabled and existing then
		existing:Destroy()
		for _, name in { "DR_TrailTop", "DR_TrailBottom" } do
			local attachment = root:FindFirstChild(name)
			if attachment then
				attachment:Destroy()
			end
		end
	end
end

function Shop.applyPerks(player, character)
	character = character or player.Character
	if not character then
		return
	end
	local humanoid = character:FindFirstChildOfClass("Humanoid")
	if humanoid then
		humanoid.WalkSpeed = player:GetAttribute("Perk_Speed") and Config.SPEED_BOOST or StarterPlayer.CharacterWalkSpeed
	end
	local root = character:FindFirstChild("HumanoidRootPart")
	if root then
		setTrail(root, player:GetAttribute("Perk_Trail") == true)
	end
end

local function grantPass(player, key)
	if player:GetAttribute("Pass_" .. key) then
		return
	end
	player:SetAttribute("Pass_" .. key, true)
	player:SetAttribute("Perk_" .. key, true) -- activé par défaut, le joueur peut le couper
	Shop.applyPerks(player)
end

local function checkPasses(player)
	for key, pass in Config.GAMEPASSES do
		if pass.id ~= 0 then
			local ok, owns = pcall(MarketplaceService.UserOwnsGamePassAsync, MarketplaceService, player.UserId, pass.id)
			if ok and owns and player.Parent then
				grantPass(player, key)
			end
		end
	end
end

---------------------------------------------------------------------------
-- Produits développeur (passer des niveaux)
---------------------------------------------------------------------------
local function processReceipt(receipt)
	local product = productsById[receipt.ProductId]
	if not product then
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	local player = Players:GetPlayerByUserId(receipt.PlayerId)
	local session = player and api.getSession(player)
	if not session or not session.ready then
		-- joueur parti ou données pas encore chargées : Roblox renverra le reçu plus tard
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end

	-- Déjà donné (reçu renvoyé par Roblox) : on ne le donne pas deux fois
	if table.find(session.receipts, receipt.PurchaseId) then
		return Enum.ProductPurchaseDecision.PurchaseGranted
	end

	api.skipStages(player, product.stages)
	table.insert(session.receipts, receipt.PurchaseId)
	while #session.receipts > MAX_RECEIPTS do
		table.remove(session.receipts, 1)
	end

	if api.canSave(session) and not api.save(player, session) then
		-- La sauvegarde a échoué : Roblox réessaiera, et le reçu est déjà noté pour éviter un doublon
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end

	api.notify(player, product.icon .. " " .. product.name .. " : merci pour ton achat !")
	return Enum.ProductPurchaseDecision.PurchaseGranted
end

---------------------------------------------------------------------------
function Shop.init(options)
	api = options

	MarketplaceService.ProcessReceipt = processReceipt

	MarketplaceService.PromptGamePassPurchaseFinished:Connect(function(player, passId, purchased)
		local key = passKeyById[passId]
		if purchased and key then
			grantPass(player, key)
			local pass = Config.GAMEPASSES[key]
			api.notify(player, pass.icon .. " " .. pass.name .. " débloqué !")
		end
	end)

	-- Le joueur active / désactive un Game Pass qu'il possède
	options.setPerkRemote.OnServerEvent:Connect(function(player, key, enabled)
		if type(key) ~= "string" or Config.GAMEPASSES[key] == nil then
			return
		end
		if not player:GetAttribute("Pass_" .. key) then
			return
		end
		player:SetAttribute("Perk_" .. key, enabled == true)
		Shop.applyPerks(player)
	end)
end

function Shop.onPlayerAdded(player)
	task.spawn(checkPasses, player)
end

return Shop
