-- Client : anime les pièges, détecte les morts, affiche l'interface (LocalScript dans StarterPlayerScripts)
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local CollectionService = game:GetService("CollectionService")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local player = Players.LocalPlayer
local Config = require(ReplicatedStorage:WaitForChild("DeathrunShared"):WaitForChild("Config"))
local TAGS = Config.TAGS

local remotes = ReplicatedStorage:WaitForChild(Config.REMOTES_NAME)
local KillMe = remotes:WaitForChild("KillMe")
local ChangeStage = remotes:WaitForChild("ChangeStage")
local Notify = remotes:WaitForChild("Notify")

local ACTIVE_RADIUS = 160 -- on n'anime que les pièges proches du joueur
local KILL_RADIUS = 40

---------------------------------------------------------------------------
-- Pièges animés (tous les joueurs voient la même chose grâce à l'heure du serveur)
---------------------------------------------------------------------------
local tracked = {} -- [part] = info
local killParts = {} -- [part] = connexion Touched
local active = {} -- liste des pièces animées proches
local overlapParams = OverlapParams.new()
overlapParams.FilterType = Enum.RaycastFilterType.Include
overlapParams.FilterDescendantsInstances = {}

local function track(part, kind)
	if not part:IsA("BasePart") or tracked[part] then
		return
	end
	tracked[part] = {
		kind = kind,
		baseCF = part:GetAttribute("BaseCF") or part.CFrame,
		speed = part:GetAttribute("Speed") or 1,
		phase = part:GetAttribute("Phase") or 0,
		amplitude = part:GetAttribute("Amplitude") or Vector3.zero,
		period = math.max(0.5, part:GetAttribute("Period") or 3),
		onFraction = part:GetAttribute("OnFraction") or 0.5,
		on = true,
		state = nil,
	}
end

local function isLethal(part)
	local info = tracked[part]
	return not (info and info.kind == "Laser" and not info.on)
end

local function cycle(info, t)
	return ((t / info.period) + info.phase) % 1
end

local function animate(part, info, t)
	local kind = info.kind
	if kind == "Spin" then
		part.CFrame = info.baseCF * CFrame.Angles(0, info.phase + t * info.speed, 0)
	elseif kind == "Move" then
		part.CFrame = info.baseCF + info.amplitude * math.sin(cycle(info, t) * math.pi * 2)
	elseif kind == "Fade" then
		local c = cycle(info, t)
		local state = (c >= info.onFraction) and "off" or ((c > info.onFraction - 0.15) and "warn" or "on")
		if state ~= info.state then
			info.state = state
			part.CanCollide = state ~= "off"
			part.Transparency = (state == "off" and 0.85) or (state == "warn" and 0.45) or 0
		end
	elseif kind == "Laser" then
		local on = cycle(info, t) < info.onFraction
		if on ~= info.state then
			info.state = on
			info.on = on
			part.CanTouch = on
			part.Transparency = on and 0.2 or 0.92
		end
	end
end

for kind, tag in { Spin = TAGS.Spin, Move = TAGS.Move, Fade = TAGS.Fade, Laser = TAGS.Laser } do
	for _, part in CollectionService:GetTagged(tag) do
		track(part, kind)
	end
	CollectionService:GetInstanceAddedSignal(tag):Connect(function(part)
		track(part, kind)
	end)
	CollectionService:GetInstanceRemovedSignal(tag):Connect(function(part)
		tracked[part] = nil
	end)
end

---------------------------------------------------------------------------
-- Morts
---------------------------------------------------------------------------
local dead = false

local function isMine(hit)
	local character = player.Character
	return character ~= nil and hit:IsDescendantOf(character)
end

local function tryKill()
	if dead then
		return
	end
	local character = player.Character
	local humanoid = character and character:FindFirstChildOfClass("Humanoid")
	if humanoid and humanoid.Health > 0 then
		dead = true
		KillMe:FireServer()
	end
end

local function trackKill(part)
	if not part:IsA("BasePart") or killParts[part] then
		return
	end
	killParts[part] = part.Touched:Connect(function(hit)
		if isMine(hit) and isLethal(part) then
			tryKill()
		end
	end)
end

for _, part in CollectionService:GetTagged(TAGS.Kill) do
	trackKill(part)
end
CollectionService:GetInstanceAddedSignal(TAGS.Kill):Connect(trackKill)
CollectionService:GetInstanceRemovedSignal(TAGS.Kill):Connect(function(part)
	local connection = killParts[part]
	if connection then
		connection:Disconnect()
		killParts[part] = nil
	end
end)

player.CharacterAdded:Connect(function(character)
	dead = false
	local humanoid = character:WaitForChild("Humanoid")
	humanoid.Died:Connect(function()
		dead = true
	end)
end)

-- Liste des pièces proches, recalculée deux fois par seconde
local function refreshActive()
	local character = player.Character
	local root = character and character:FindFirstChild("HumanoidRootPart")
	table.clear(active)
	if not root then
		overlapParams.FilterDescendantsInstances = {}
		return
	end
	local position = root.Position
	for part, info in tracked do
		if (info.baseCF.Position - position).Magnitude < ACTIVE_RADIUS then
			table.insert(active, part)
		end
	end
	local nearbyKill = {}
	for part in killParts do
		if (part.Position - position).Magnitude - part.Size.Magnitude / 2 < KILL_RADIUS then
			table.insert(nearbyKill, part)
		end
	end
	overlapParams.FilterDescendantsInstances = nearbyKill
end

-- Sécurité en plus de Touched : un piège qui bouge peut "entrer" dans un joueur immobile
local function overlapCheck()
	local character = player.Character
	if dead or not character then
		return
	end
	for _, bodyPart in character:GetChildren() do
		if bodyPart:IsA("BasePart") then
			for _, hit in workspace:GetPartsInPart(bodyPart, overlapParams) do
				if isLethal(hit) then
					tryKill()
					return
				end
			end
		end
	end
end

local refreshTimer, overlapTimer = 0, 0
RunService.Heartbeat:Connect(function(dt)
	refreshTimer += dt
	if refreshTimer >= 0.5 then
		refreshTimer = 0
		refreshActive()
	end

	local t = workspace:GetServerTimeNow()
	for _, part in active do
		local info = tracked[part]
		if info then
			animate(part, info, t)
		end
	end

	overlapTimer += dt
	if overlapTimer >= 0.1 then
		overlapTimer = 0
		overlapCheck()
	end
end)

---------------------------------------------------------------------------
-- Interface
---------------------------------------------------------------------------
local function create(className, props, children)
	local instance = Instance.new(className)
	for key, value in props do
		instance[key] = value
	end
	for _, child in children or {} do
		child.Parent = instance
	end
	return instance
end

local function corner(radius)
	return create("UICorner", { CornerRadius = UDim.new(0, radius) })
end

local gui = create("ScreenGui", { Name = "DeathrunUI", ResetOnSpawn = false })

local panel = create("Frame", {
	AnchorPoint = Vector2.new(0.5, 0),
	Position = UDim2.new(0.5, 0, 0, 8),
	Size = UDim2.fromOffset(330, 70),
	BackgroundColor3 = Color3.fromRGB(20, 20, 30),
	BackgroundTransparency = 0.2,
	Parent = gui,
}, { corner(12) })

local title = create("TextLabel", {
	Position = UDim2.fromOffset(50, 6),
	Size = UDim2.new(1, -100, 0, 28),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBlack,
	TextScaled = true,
	TextColor3 = Color3.new(1, 1, 1),
	Text = "Niveau 1 / " .. Config.TOTAL_STAGES,
	Parent = panel,
})

local barBack = create("Frame", {
	Position = UDim2.fromOffset(50, 38),
	Size = UDim2.new(1, -100, 0, 10),
	BackgroundColor3 = Color3.fromRGB(60, 60, 75),
	Parent = panel,
}, { corner(5) })

local barFill = create("Frame", {
	Size = UDim2.fromScale(0, 1),
	BackgroundColor3 = Color3.fromRGB(60, 230, 90),
	Parent = barBack,
}, { corner(5) })

local recordLabel = create("TextLabel", {
	Position = UDim2.fromOffset(50, 50),
	Size = UDim2.new(1, -100, 0, 16),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamMedium,
	TextScaled = true,
	TextColor3 = Color3.fromRGB(200, 200, 215),
	Text = "",
	Parent = panel,
})

local function button(text, xScale, xOffset)
	return create("TextButton", {
		AnchorPoint = Vector2.new(xScale, 0.5),
		Position = UDim2.new(xScale, xOffset, 0.5, 0),
		Size = UDim2.fromOffset(38, 50),
		BackgroundColor3 = Color3.fromRGB(70, 70, 95),
		Font = Enum.Font.GothamBlack,
		TextScaled = true,
		TextColor3 = Color3.new(1, 1, 1),
		Text = text,
		Parent = panel,
	}, { corner(10) })
end

local prevButton = button("◀", 0, 6)
local nextButton = button("▶", 1, -6)

local maxButton = create("TextButton", {
	AnchorPoint = Vector2.new(0.5, 0),
	Position = UDim2.new(0.5, 0, 0, 82),
	Size = UDim2.fromOffset(170, 30),
	BackgroundColor3 = Color3.fromRGB(255, 170, 40),
	Font = Enum.Font.GothamBold,
	TextScaled = true,
	TextColor3 = Color3.new(1, 1, 1),
	Text = "Aller à mon record",
	Visible = false,
	Parent = gui,
}, { corner(10), create("UIPadding", { PaddingTop = UDim.new(0, 5), PaddingBottom = UDim.new(0, 5) }) })

local toast = create("TextLabel", {
	AnchorPoint = Vector2.new(0.5, 0.5),
	Position = UDim2.fromScale(0.5, 0.35),
	Size = UDim2.new(0.8, 0, 0, 60),
	BackgroundTransparency = 1,
	Font = Enum.Font.GothamBlack,
	TextScaled = true,
	TextColor3 = Color3.fromRGB(255, 220, 60),
	TextStrokeTransparency = 0,
	TextTransparency = 1,
	TextStrokeColor3 = Color3.new(0, 0, 0),
	Text = "",
	Parent = gui,
})

gui.Parent = player:WaitForChild("PlayerGui")

local function stats()
	return player:GetAttribute("Stage") or 1, player:GetAttribute("MaxStage") or 1, player:GetAttribute("Wins") or 0
end

local function refreshUI()
	local stage, maxStage, wins = stats()
	title.Text = "Niveau " .. stage .. " / " .. Config.TOTAL_STAGES
	TweenService:Create(barFill, TweenInfo.new(0.3), {
		Size = UDim2.fromScale((stage - 1) / Config.TOTAL_STAGES, 1),
	}):Play()
	recordLabel.Text = "Record : " .. maxStage .. (wins > 0 and ("   •   Victoires : " .. wins) or "")
	prevButton.Visible = stage > 1
	nextButton.Visible = stage < maxStage
	maxButton.Visible = stage < maxStage
end

player:GetAttributeChangedSignal("Stage"):Connect(refreshUI)
player:GetAttributeChangedSignal("MaxStage"):Connect(refreshUI)
player:GetAttributeChangedSignal("Wins"):Connect(refreshUI)
refreshUI()

prevButton.Activated:Connect(function()
	local stage = stats()
	ChangeStage:FireServer(stage - 1)
end)
nextButton.Activated:Connect(function()
	local stage = stats()
	ChangeStage:FireServer(stage + 1)
end)
maxButton.Activated:Connect(function()
	local _, maxStage = stats()
	ChangeStage:FireServer(maxStage)
end)

local toastId = 0
Notify.OnClientEvent:Connect(function(message)
	toastId += 1
	local id = toastId
	toast.Text = message
	toast.TextTransparency = 0
	toast.TextStrokeTransparency = 0
	task.delay(3, function()
		if id == toastId then
			TweenService:Create(toast, TweenInfo.new(0.6), { TextTransparency = 1, TextStrokeTransparency = 1 }):Play()
		end
	end)
end)
