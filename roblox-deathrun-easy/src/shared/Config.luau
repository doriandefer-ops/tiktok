-- Config partagée entre le serveur et les joueurs (ModuleScript dans ReplicatedStorage)
local Config = {}

Config.TOTAL_STAGES = 500 -- nombre de niveaux
Config.STAGES_PER_ROW = 25 -- niveaux par rangée (20 rangées de 25)
Config.STAGE_LENGTH = 80 -- longueur d'un niveau (studs, axe X)
Config.ROW_SPACING = 70 -- écart entre deux rangées (studs, axe Z)
Config.BASE_HEIGHT = 50 -- hauteur des plateformes
Config.START_SIZE = 16 -- plateforme de départ : de x = 0 à x = 16
Config.FINISH_SIZE = 12 -- plateforme d'arrivée : de x = 64 à x = 76
Config.FINISH_X = 70 -- centre de la plateforme d'arrivée
Config.SEED = 2026 -- change ce nombre pour obtenir 500 autres niveaux

Config.MAP_NAME = "DeathrunMap"
Config.REMOTES_NAME = "DeathrunRemotes"
Config.DATASTORE_NAME = "DeathrunEasy_v1"

---------------------------------------------------------------------------
-- BOUTIQUE : colle ici les numéros (ID) de tes articles créés sur Roblox (voir README).
-- Tant qu'un ID vaut 0, l'article s'affiche "pas encore disponible".
---------------------------------------------------------------------------
Config.PRODUCTS = { -- Produits développeur (achetables plusieurs fois)
	SkipStage = { id = 0, stages = 1, name = "Passer le niveau", icon = "⏭" },
	Skip10 = { id = 0, stages = 10, name = "Passer 10 niveaux", icon = "⏩" },
}
Config.GAMEPASSES = { -- Game Pass (achetés une seule fois, pour toujours)
	Speed = { id = 0, name = "Vitesse ×2", icon = "⚡" },
	Trail = { id = 0, name = "Traînée arc-en-ciel", icon = "🌈" },
}
Config.SHOP_ORDER = { "SkipStage", "Skip10", "Speed", "Trail" }
Config.SPEED_BOOST = 32 -- vitesse avec le Game Pass (normale : 16)
Config.DEATHS_BEFORE_HINT = 3 -- après 3 morts sur le même niveau : "Bloqué ? Passe le niveau !"

Config.TAGS = {
	Kill = "DR_Kill", -- touche = mort
	Finish = "DR_Finish", -- fin du niveau (checkpoint)
	Spin = "DR_Spin", -- barre qui tourne
	Move = "DR_Move", -- bloc qui fait des allers-retours
	Fade = "DR_Fade", -- dalle qui disparaît
	Laser = "DR_Laser", -- laser qui s'allume / s'éteint
}

-- Coin "début" du niveau : x = début de la plateforme de départ, y = dessus des plateformes, z = axe du chemin
function Config.getStageOrigin(stage)
	local index = stage - 1
	local col = index % Config.STAGES_PER_ROW
	local row = math.floor(index / Config.STAGES_PER_ROW)
	return CFrame.new(col * Config.STAGE_LENGTH, Config.BASE_HEIGHT, row * Config.ROW_SPACING)
end

-- Point d'apparition du joueur sur un niveau, tourné vers la sortie (+X)
function Config.getSpawnCFrame(stage)
	return Config.getStageOrigin(stage)
		* CFrame.new(Config.START_SIZE / 2, 3.5, 0)
		* CFrame.Angles(0, -math.pi / 2, 0)
end

return Config
