-- Génère les 500 niveaux au lancement du serveur (ModuleScript dans ServerScriptService)
-- Chaque niveau : plateforme de départ (16 studs) -> zone d'obstacle (48 studs) -> plateforme d'arrivée verte.
-- Tous les sauts sont calibrés pour un personnage par défaut (WalkSpeed 16, saut ~7 studs) :
-- aucun trou ne dépasse 5,5 studs, donc tout reste "easy".
local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("DeathrunShared"):WaitForChild("Config"))
local TAGS = Config.TAGS

local ZONE_START = Config.START_SIZE -- 16
local ZONE_END = Config.FINISH_X - Config.FINISH_SIZE / 2 -- 64
local ZONE_LEN = ZONE_END - ZONE_START -- 48
local MAX_EASY_GAP = 5.5

local KILL_COLOR = Color3.fromRGB(255, 45, 45)
local FINISH_COLOR = Color3.fromRGB(60, 230, 90)
local START_COLOR = Color3.fromRGB(235, 235, 245)
local DARK_COLOR = Color3.fromRGB(45, 45, 55)

local Generator = {}

---------------------------------------------------------------------------
-- Outils de construction
---------------------------------------------------------------------------

local function applyProps(part, ctx, size, localCFrame, props)
	part.Anchored = true
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Material = Enum.Material.SmoothPlastic
	part.Color = ctx.color
	part.Size = size
	part.CFrame = ctx.origin * localCFrame

	local tags = nil
	if props then
		for key, value in props do
			if key == "Tags" then
				tags = value
			elseif key == "Attributes" then
				for name, attr in value do
					part:SetAttribute(name, attr)
				end
			else
				part[key] = value
			end
		end
	end

	if tags then
		for _, tag in tags do
			CollectionService:AddTag(part, tag)
		end
		-- Les pièces animées gardent leur position de départ pour que les joueurs les animent
		if table.find(tags, TAGS.Spin) or table.find(tags, TAGS.Move) then
			part:SetAttribute("BaseCF", part.CFrame)
		end
	end

	-- Parent en dernier : tags + attributs sont répliqués en même temps que la pièce
	part.Parent = ctx.folder
	return part
end

local function makePart(ctx, size, localCFrame, props)
	return applyProps(Instance.new("Part"), ctx, size, localCFrame, props)
end

-- Plateforme dont le dessus est à la hauteur `top` (repère local du niveau)
local function platform(ctx, x0, x1, z, width, top, props)
	return makePart(ctx, Vector3.new(x1 - x0, 1, width), CFrame.new((x0 + x1) / 2, top - 0.5, z), props)
end

local function killPart(ctx, size, localCFrame, props)
	local merged = {
		Name = "Kill",
		Color = KILL_COLOR,
		Material = Enum.Material.Neon,
		Tags = { TAGS.Kill },
	}
	if props then
		for key, value in props do
			merged[key] = value
		end
	end
	return makePart(ctx, size, localCFrame, merged)
end

-- Répartit n plateformes de taille `size` sur toute la zone, avec des trous réguliers <= maxGap
local function fitRow(size, wantedGap, maxGap)
	local n = math.max(1, math.floor((ZONE_LEN - wantedGap) / (size + wantedGap)))
	local gap = (ZONE_LEN - n * size) / (n + 1)
	while gap > maxGap do
		n += 1
		gap = (ZONE_LEN - n * size) / (n + 1)
	end
	return n, gap
end

local function addLabel(part, text)
	local billboard = Instance.new("BillboardGui")
	billboard.Name = "StageLabel"
	billboard.Size = UDim2.fromScale(10, 3)
	billboard.StudsOffset = Vector3.new(0, 7, 0)
	billboard.MaxDistance = 90

	local label = Instance.new("TextLabel")
	label.Size = UDim2.fromScale(1, 1)
	label.BackgroundTransparency = 1
	label.Text = text
	label.TextScaled = true
	label.Font = Enum.Font.GothamBlack
	label.TextColor3 = Color3.new(1, 1, 1)
	label.TextStrokeTransparency = 0.2
	label.Parent = billboard

	billboard.Parent = part
end

---------------------------------------------------------------------------
-- Obstacles (d = difficulté de 0 au niveau 1 à 1 au niveau 500, toujours facile)
---------------------------------------------------------------------------

local Obstacles = {}

-- Sauts de plateforme en plateforme
function Obstacles.jumps(ctx)
	local d, rng = ctx.d, ctx.rng
	local size = 7 - 2 * d
	local n, gap = fitRow(size, 3 + 2 * d, MAX_EASY_GAP)
	local x, z = ZONE_START, 0
	for _ = 1, n do
		x += gap
		z = math.clamp(z + rng:NextNumber(-1, 1) * (1.5 + 2 * d), -4, 4)
		platform(ctx, x, x + size, z, size, rng:NextNumber(0, 1.2))
		x += size
	end
end

-- Pont avec des petites barres rouges à sauter
function Obstacles.hurdles(ctx)
	local d, rng = ctx.d, ctx.rng
	local width = 8 - 3 * d
	platform(ctx, ZONE_START, ZONE_END, 0, width, 0)
	local count = 2 + math.floor(3 * d + rng:NextNumber(0, 0.99))
	local height = 1 + 0.5 * d
	for i = 1, count do
		local x = ZONE_START + ZONE_LEN * i / (count + 1)
		killPart(ctx, Vector3.new(1, height, width), CFrame.new(x, height / 2, 0))
	end
end

-- Barres qui tournent au ras du sol : il faut sauter par-dessus
function Obstacles.spinners(ctx)
	local d, rng = ctx.d, ctx.rng
	local width = 14
	platform(ctx, ZONE_START, ZONE_END, 0, width, 0)
	local count = 1 + (d > 0.35 and 1 or 0) + (d > 0.75 and 1 or 0)
	local barLength = math.min(width - 1, ZONE_LEN / (count + 1) - 1)
	for i = 1, count do
		local x = ZONE_START + ZONE_LEN * i / (count + 1)
		local direction = rng:NextNumber() < 0.5 and -1 or 1
		makePart(ctx, Vector3.new(1.2, 0.4, 1.2), CFrame.new(x, 0.2, 0), { Name = "Hub", Color = DARK_COLOR })
		killPart(ctx, Vector3.new(1, 1, barLength), CFrame.new(x, 1, 0), {
			Name = "Spinner",
			CanCollide = false,
			Tags = { TAGS.Kill, TAGS.Spin },
			Attributes = {
				Speed = (1 + 1.5 * d) * direction, -- radians / seconde
				Phase = rng:NextNumber(0, math.pi * 2),
			},
		})
	end
end

-- Blocs rouges qui glissent de gauche à droite
function Obstacles.movers(ctx)
	local d, rng = ctx.d, ctx.rng
	local width = 10
	platform(ctx, ZONE_START, ZONE_END, 0, width, 0)
	local count = 2 + math.floor(2 * d + rng:NextNumber(0, 0.99))
	local period = 4 - 1.5 * d
	for i = 1, count do
		local x = ZONE_START + ZONE_LEN * i / (count + 1)
		killPart(ctx, Vector3.new(3, 3, 3), CFrame.new(x, 1.5, 0), {
			Name = "Mover",
			CanCollide = false,
			Tags = { TAGS.Kill, TAGS.Move },
			Attributes = {
				Amplitude = Vector3.new(0, 0, (width - 3) / 2),
				Period = period,
				Phase = rng:NextNumber(),
			},
		})
	end
end

-- Dalles qui clignotent puis disparaissent un instant
function Obstacles.faders(ctx)
	local d = ctx.d
	local size = 6 - d
	local n, gap = fitRow(size, 1.5, 2.5)
	local x = ZONE_START
	for i = 1, n do
		x += gap
		platform(ctx, x, x + size, 0, size, 0, {
			Name = "Fader",
			Color = ctx.color:Lerp(Color3.new(1, 1, 1), 0.35),
			Tags = { TAGS.Fade },
			Attributes = {
				Period = 4,
				OnFraction = 0.7 - 0.15 * d,
				Phase = i * 0.15,
			},
		})
		x += size
	end
end

-- Murs laser qui s'allument et s'éteignent
function Obstacles.lasers(ctx)
	local d, rng = ctx.d, ctx.rng
	local width = 8
	platform(ctx, ZONE_START, ZONE_END, 0, width, 0)
	local count = 2 + math.floor(2 * d + rng:NextNumber(0, 0.99))
	for i = 1, count do
		local x = ZONE_START + ZONE_LEN * i / (count + 1)
		for side = -1, 1, 2 do
			makePart(ctx, Vector3.new(1, 9, 1), CFrame.new(x, 4.5, side * (width / 2 + 0.5)), {
				Name = "LaserPost",
				Color = DARK_COLOR,
			})
		end
		killPart(ctx, Vector3.new(0.4, 8, width), CFrame.new(x, 4, 0), {
			Name = "Laser",
			CanCollide = false,
			Transparency = 0.2,
			Tags = { TAGS.Kill, TAGS.Laser },
			Attributes = {
				Period = 3,
				OnFraction = 0.4 + 0.2 * d,
				Phase = rng:NextNumber(),
			},
		})
	end
end

-- Escalier qui monte puis redescend
function Obstacles.stairs(ctx)
	local d, rng = ctx.d, ctx.rng
	local width = 6
	local rise = 1.5
	local stepLen = 4
	local function column(x0, x1, top)
		makePart(ctx, Vector3.new(x1 - x0, top + 1, width), CFrame.new((x0 + x1) / 2, (top - 1) / 2, 0))
	end
	local x = ZONE_START
	for i = 1, 5 do
		column(x, x + stepLen, i * rise)
		x += stepLen
	end
	column(x, x + 8, 6 * rise)
	if d > 0.3 then
		killPart(ctx, Vector3.new(1, 1, width), CFrame.new(x + 4, 6 * rise + 0.5, 0))
	end
	x += 8
	for i = 5, 1, -1 do
		column(x, x + stepLen, i * rise)
		x += stepLen
	end
	-- petit bonus visuel
	if rng:NextNumber() < 0.5 then
		makePart(ctx, Vector3.new(1, 3, 1), CFrame.new(ZONE_START + 24, 6 * rise + 1.5, width / 2 - 0.5), {
			Name = "Deco",
			Material = Enum.Material.Neon,
		})
	end
end

-- Poutres étroites en zigzag
function Obstacles.zigzag(ctx)
	local d = ctx.d
	local width = 3.4 - 0.8 * d
	local segment = 8
	for i = 0, ZONE_LEN / segment - 1 do
		local x0 = ZONE_START + i * segment
		local z = (i % 2 == 0) and -0.8 or 0.8
		platform(ctx, x0, x0 + segment, z, width, 0)
	end
end

local EASY_START = { "jumps", "hurdles", "stairs" }
local ALL_OBSTACLES = { "jumps", "hurdles", "spinners", "movers", "faders", "lasers", "stairs", "zigzag" }

local function pickObstacle(stage, rng, previous)
	local pool = stage <= 10 and EASY_START or ALL_OBSTACLES
	local choice
	repeat
		choice = pool[rng:NextInteger(1, #pool)]
	until choice ~= previous
	return choice
end

---------------------------------------------------------------------------
-- Niveaux
---------------------------------------------------------------------------

local function buildStage(stage, map, previous)
	local model = Instance.new("Model")
	model.Name = "Stage" .. stage

	local rng = Random.new(stage * 7919 + Config.SEED)
	local ctx = {
		origin = Config.getStageOrigin(stage),
		folder = model,
		rng = rng,
		d = (stage - 1) / math.max(1, Config.TOTAL_STAGES - 1),
		color = Color3.fromHSV(((stage - 1) * 0.037) % 1, 0.6, 0.95),
	}

	-- Départ (le niveau 1 sert aussi de SpawnLocation)
	local start
	if stage == 1 then
		start = Instance.new("SpawnLocation")
		start.Neutral = true
		start.Duration = 0
	else
		start = Instance.new("Part")
	end
	applyProps(start, ctx, Vector3.new(Config.START_SIZE, 1, Config.START_SIZE), CFrame.new(Config.START_SIZE / 2, -0.5, 0), {
		Name = "Start",
		Color = START_COLOR,
	})
	addLabel(start, "Niveau " .. stage)

	-- Obstacle
	local obstacle = pickObstacle(stage, rng, previous)
	Obstacles[obstacle](ctx)
	model:SetAttribute("Obstacle", obstacle)

	-- Arrivée
	makePart(ctx, Vector3.new(Config.FINISH_SIZE, 1, Config.FINISH_SIZE), CFrame.new(Config.FINISH_X, -0.5, 0), {
		Name = "Finish",
		Color = FINISH_COLOR,
		Material = Enum.Material.Neon,
		Tags = { TAGS.Finish },
		Attributes = { Stage = stage },
	})

	model.Parent = map
	return obstacle
end

local function buildLava(map)
	local rows = math.ceil(Config.TOTAL_STAGES / Config.STAGES_PER_ROW)
	local length = Config.STAGES_PER_ROW * Config.STAGE_LENGTH + 40 -- 2040 studs (max Roblox : 2048)
	for row = 0, rows - 1 do
		local lava = Instance.new("Part")
		lava.Name = "Lava"
		lava.Anchored = true
		lava.Size = Vector3.new(length, 2, Config.ROW_SPACING)
		lava.CFrame = CFrame.new(length / 2 - 20, Config.BASE_HEIGHT - 30, row * Config.ROW_SPACING)
		lava.Material = Enum.Material.CrackedLava
		lava.Color = Color3.fromRGB(255, 90, 20)
		CollectionService:AddTag(lava, TAGS.Kill)
		lava.Parent = map
	end
end

function Generator.build()
	local existing = workspace:FindFirstChild(Config.MAP_NAME)
	if existing then
		existing:Destroy()
	end

	local map = Instance.new("Folder")
	map.Name = Config.MAP_NAME
	map.Parent = workspace

	buildLava(map)

	local previous = nil
	for stage = 1, Config.TOTAL_STAGES do
		previous = buildStage(stage, map, previous)
		if stage % 10 == 0 then
			task.wait() -- évite de bloquer le serveur pendant la génération
		end
	end
	return map
end

Generator.Obstacles = Obstacles
return Generator
