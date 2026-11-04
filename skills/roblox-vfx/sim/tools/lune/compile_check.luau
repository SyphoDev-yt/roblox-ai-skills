-- Compile-check Luau files (syntax + compile errors) with Lune's luau compiler.
local fs = require("@lune/fs")
local luau = require("@lune/luau")
local process = require("@lune/process")

local bad = 0
for _, path in process.args do
	local src = fs.readFile(path)
	local ok, err = pcall(luau.compile, src)
	if ok then
		print("OK   " .. path)
	else
		bad += 1
		print("FAIL " .. path .. "\n     " .. tostring(err))
	end
end
process.exit(bad)
