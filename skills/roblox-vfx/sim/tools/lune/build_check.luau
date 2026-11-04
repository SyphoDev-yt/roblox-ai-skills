-- Run a kit's buildTemplate() against Lune's Roblox reflection (real class and
-- property definitions), with every asset id faked. Catches wrong property
-- names, wrong value types and wrong enum items before Studio does.
local fs = require("@lune/fs")
local luau = require("@lune/luau")
local process = require("@lune/process")
local roblox = require("@lune/roblox")

local game = roblox.Instance.new("DataModel")
local env = {}
for k, v in roblox do env[k] = v end
-- CreateMeshPartAsync is not in Lune: stub it so mesh parts come out as MeshParts (else every one falls
-- back to a Part and the SurfaceAppearance-parent check below cannot tell the real offenders apart)
local assetStub = { CreateMeshPartAsync = function(_, _uri) return roblox.Instance.new("MeshPart") end }
env.game = setmetatable({
	GetService = function(_, n) if n == "AssetService" then return assetStub end return game:GetService(n) end,
}, { __index = function(_, k) return game[k] end })
env.workspace = game:GetService("Workspace")
env.warn = function(...) end
env.task = { delay = function() end, wait = function() end }
env.math, env.table, env.string, env.pcall, env.tostring, env.ipairs, env.pairs, env.print, env.error, env.type, env.typeof, env.os =
	math, table, string, pcall, tostring, ipairs, pairs, print, error, type, typeof, os
setmetatable(env, { __index = function(_, k) error("global not available in check: " .. tostring(k)) end })

local bad = 0
for _, path in process.args do
	local src = fs.readFile(path)
	local fn = luau.load(src, { debugName = path, environment = env })
	local ok, M = pcall(fn)
	if not ok then
		bad += 1
		print("LOAD FAIL " .. path .. ": " .. tostring(M))
		continue
	end
	local assets = { textures = {}, meshes = {} }
	for _, id in M.NEEDS.textures do assets.textures[id] = "rbxassetid://1" end
	for _, id in M.NEEDS.meshes do assets.meshes[id] = "rbxassetid://2" end
	local ok2, res = pcall(M.buildTemplate, assets, game:GetService("ReplicatedStorage"))
	-- Studio refuses a SurfaceAppearance under anything but a MeshPart (Kurohitsugi v5); Lune does not
	if ok2 then
		local saBad = {}
		for _, d in res:GetDescendants() do
			if d.ClassName == "SurfaceAppearance" and not (d.Parent and d.Parent.ClassName == "MeshPart") then
				table.insert(saBad, (d.Parent and d.Parent.Name or "?") .. "(" .. (d.Parent and d.Parent.ClassName or "nil") .. ")")
			end
		end
		if #saBad > 0 then
			ok2, res = false, "SurfaceAppearance can only be parented to MeshParts: " .. table.concat(saBad, ", ")
		end
	end
	if ok2 then
		local fails = {}
		for k in M.PROP_FAILS do table.insert(fails, k) end
		table.sort(fails)
		print(string.format("OK   %s  %d instances; unsettable: %s", path:match("[^/]+$"), #res:GetDescendants(), table.concat(fails, ", ")))
	else
		bad += 1
		print("BUILD FAIL " .. path:match("[^/]+$") .. ": " .. tostring(res))
	end
end
process.exit(bad)
