-- Serveur : génère la carte, gère la progression, les checkpoints et la sauvegarde
local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("DeathrunShared"):WaitForChild("Config"))
local Generator = require(script.Parent:WaitForChild("LevelGenerator"))
local Shop = require(script.Parent:WaitForChild("Shop"))

Players.RespawnTime = 1

---------------------------------------------------------------------------
-- RemoteEvents
---------------------------------------------------------------------------
local remotes = Instance.new("Folder")
remotes.Name = Config.REMOTES_NAME

local function newRemote(name)
	local remote = Instance.new("RemoteEvent")
	remote.Name = name
	remote.Parent = remotes
	return remote
end

local KillMe = newRemote("KillMe") -- client -> serveur : "j'ai touché un piège"
local ChangeStage = newRemote("ChangeStage") -- client -> serveur : aller à un niveau déjà débloqué
local Notify = newRemote("Notify") -- serveur -> client : message à afficher
local SetPerk = newRemote("SetPerk") -- client -> serveur : activer / couper un Game Pass
remotes.Parent = ReplicatedStorage

---------------------------------------------------------------------------
-- Sauvegarde
---------------------------------------------------------------------------
local store = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore(Config.DATASTORE_NAME)
	end)
	if ok then
		store = result
	else
		warn("[Deathrun] DataStore indisponible, la progression ne sera pas sauvegardée :", result)
	end
end

local sessions = {} -- [Player] = { stage, max, wins, receipts, loaded, ready, busy, lastRequest, ... }
local mapReady = false

local function dataKey(player)
	return "player_" .. player.UserId
end

local function loadData(player)
	if not store then
		return nil, false
	end
	for attempt = 1, 3 do
		local ok, result = pcall(store.GetAsync, store, dataKey(player))
		if ok then
			return result, true
		end
		warn("[Deathrun] Chargement échoué (essai " .. attempt .. ") :", result)
		task.wait(attempt)
	end
	return nil, false
end

local function saveData(player, session)
	-- Si le chargement a échoué on n'écrase pas l'ancienne sauvegarde
	if not store or not session.loaded then
		return false
	end
	local payload = { stage = session.stage, max = session.max, wins = session.wins, receipts = session.receipts }
	local ok, err = pcall(store.SetAsync, store, dataKey(player), payload)
	if not ok then
		warn("[Deathrun] Sauvegarde échouée pour " .. player.Name .. " :", err)
	end
	return ok
end

local function toStage(value, fallback)
	if type(value) ~= "number" or value ~= value then
		return fallback
	end
	return math.clamp(math.floor(value), 1, Config.TOTAL_STAGES)
end

---------------------------------------------------------------------------
-- Progression
---------------------------------------------------------------------------
local function publish(player, session)
	session.stageValue.Value = session.stage
	session.winsValue.Value = session.wins
	player:SetAttribute("Stage", session.stage)
	player:SetAttribute("MaxStage", session.max)
	player:SetAttribute("Wins", session.wins)
end

local function teleportToStage(player, stage)
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	if not root then
		return
	end
	local target = Config.getSpawnCFrame(stage)
	-- Avec StreamingEnabled, on charge le niveau chez le joueur avant de le téléporter
	pcall(function()
		player:RequestStreamAroundAsync(target.Position, 3)
	end)
	if character.Parent then
		character:PivotTo(target)
		root.AssemblyLinearVelocity = Vector3.zero
	end
end

-- Achat "passer des niveaux"
local function skipStages(player, count)
	local session = sessions[player]
	if not session then
		return
	end
	session.stage = math.min(Config.TOTAL_STAGES, session.stage + count)
	session.max = math.max(session.max, session.stage)
	publish(player, session)
	if mapReady then
		teleportToStage(player, session.stage)
	end
end

local function onCharacterAdded(player, character)
	local root = character:WaitForChild("HumanoidRootPart", 10)
	if not root then
		return
	end
	character:WaitForChild("Humanoid", 10)
	Shop.applyPerks(player, character)
	while not mapReady do
		task.wait(0.2)
	end
	task.wait(0.1)
	local session = sessions[player]
	if session and character.Parent then
		teleportToStage(player, session.stage)
	end
end

local function onFinishTouched(finishPart, hit)
	local character = hit:FindFirstAncestorOfClass("Model")
	local player = character and Players:GetPlayerFromCharacter(character)
	local session = player and sessions[player]
	if not session or session.busy then
		return
	end
	local humanoid = character:FindFirstChildOfClass("Humanoid")
	if not humanoid or humanoid.Health <= 0 then
		return
	end
	local stage = finishPart:GetAttribute("Stage")
	if stage ~= session.stage then
		return
	end

	session.busy = true
	local mustTeleport = false
	if stage >= Config.TOTAL_STAGES then
		session.wins += 1
		session.stage = 1
		mustTeleport = true
		Notify:FireClient(player, "🏆 BRAVO ! Tu as fini les " .. Config.TOTAL_STAGES .. " niveaux !", "win")
	else
		session.stage = stage + 1
		session.max = math.max(session.max, session.stage)
		-- Fin de rangée : le niveau suivant est sur la rangée d'à côté
		mustTeleport = (stage % Config.STAGES_PER_ROW) == 0
		if stage % 50 == 0 then
			Notify:FireClient(player, "⭐ " .. stage .. " niveaux terminés !", "milestone")
		end
	end
	publish(player, session)
	if mustTeleport then
		teleportToStage(player, session.stage)
	end
	task.delay(0.5, function()
		session.busy = false
	end)
end

---------------------------------------------------------------------------
-- Joueurs
---------------------------------------------------------------------------
local function onPlayerAdded(player)
	local session = { stage = 1, max = 1, wins = 0, receipts = {}, loaded = false, ready = false, busy = false, lastRequest = 0 }
	sessions[player] = session

	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	session.stageValue = Instance.new("IntValue")
	session.stageValue.Name = "Niveau"
	session.stageValue.Parent = leaderstats
	session.winsValue = Instance.new("IntValue")
	session.winsValue.Name = "Victoires"
	session.winsValue.Parent = leaderstats
	leaderstats.Parent = player
	publish(player, session)

	player.CharacterAdded:Connect(function(character)
		onCharacterAdded(player, character)
	end)
	if player.Character then
		task.spawn(onCharacterAdded, player, player.Character)
	end

	Shop.onPlayerAdded(player)

	local saved, ok = loadData(player)
	if not player.Parent then
		return
	end
	session.loaded = ok
	session.ready = true
	if type(saved) == "table" then
		session.stage = toStage(saved.stage, 1)
		session.max = math.max(session.stage, toStage(saved.max, 1))
		session.wins = (type(saved.wins) == "number" and saved.wins >= 0) and math.floor(saved.wins) or 0
		if type(saved.receipts) == "table" then
			for _, id in saved.receipts do
				if type(id) == "string" then
					table.insert(session.receipts, id)
				end
			end
		end
		publish(player, session)
		if mapReady and session.stage > 1 then
			teleportToStage(player, session.stage)
		end
	end
end

local function onPlayerRemoving(player)
	local session = sessions[player]
	if session then
		saveData(player, session)
		sessions[player] = nil
	end
end

KillMe.OnServerEvent:Connect(function(player)
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if humanoid and humanoid.Health > 0 then
		humanoid.Health = 0
	end
end)

ChangeStage.OnServerEvent:Connect(function(player, target)
	local session = sessions[player]
	if not session or not mapReady then
		return
	end
	local now = os.clock()
	if now - session.lastRequest < 0.3 then
		return
	end
	session.lastRequest = now
	local stage = toStage(target, nil)
	if not stage or stage > session.max or stage == session.stage then
		return
	end
	session.stage = stage
	publish(player, session)
	teleportToStage(player, stage)
end)

---------------------------------------------------------------------------
-- Démarrage
---------------------------------------------------------------------------
Shop.init({
	getSession = function(player)
		return sessions[player]
	end,
	skipStages = skipStages,
	save = saveData,
	canSave = function(session)
		return store ~= nil and session.loaded
	end,
	notify = function(player, message)
		Notify:FireClient(player, message)
	end,
	setPerkRemote = SetPerk,
})

CollectionService:GetInstanceAddedSignal(Config.TAGS.Finish):Connect(function(part)
	part.Touched:Connect(function(hit)
		onFinishTouched(part, hit)
	end)
end)

Players.PlayerAdded:Connect(onPlayerAdded)
Players.PlayerRemoving:Connect(onPlayerRemoving)
for _, player in Players:GetPlayers() do
	task.spawn(onPlayerAdded, player)
end

game:BindToClose(function()
	for player, session in sessions do
		task.spawn(saveData, player, session)
	end
	task.wait(3)
end)

-- Sauvegarde automatique toutes les 2 minutes
task.spawn(function()
	while true do
		task.wait(120)
		for player, session in sessions do
			task.spawn(saveData, player, session)
		end
	end
end)

local started = os.clock()
Generator.build()
mapReady = true
ReplicatedStorage:SetAttribute("DeathrunReady", true)
print(string.format("[Deathrun] %d niveaux générés en %.1f s", Config.TOTAL_STAGES, os.clock() - started))

-- Les joueurs arrivés pendant la génération sont placés sur leur niveau
for player, session in sessions do
	if session.stage > 1 then
		task.spawn(teleportToStage, player, session.stage)
	end
end
