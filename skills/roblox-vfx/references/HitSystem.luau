--!strict
-- HitSystem: damage feedback for the showcase target (ReplicatedStorage.Showcase.HitSystem).
-- Client-side: the director spawns the target locally, so its physics and joints are ours to drive.
--
--   local target = HitSystem.spawnTarget(CFrame)           -- R6 sparring partner with overhead health bar
--   HitSystem.Hit(target, {damage = 12, knock = Vector3.new(0, 0, -3), time = 0.2, reaction = "flinch", stun = 0.4,
--                          ultimate = false, hitstop = 0})
--       knock: a DISPLACEMENT in world studs reached after `time` s (v5: by a thrown, tumbling body, see PHYS)
--       reaction: "flinch" | "knockback" | "launch" | "ragdoll" (ragdoll stays down; the others get up)
--   HitSystem.reset(target, CFrame)                         -- full health, joints back, standing at CFrame
--       reset also undoes whatever a kit did to the target: a ScaleTo, the look of every original part, decal
--       and joint (transparency, colour, material, size, C0/C1, Enabled) and the parent of any original instance
--       a kit moved out, and it destroys anything a kit parented under the target. An original instance a kit
--       DESTROYED can't come back, so kits hide target parts instead of destroying them.
--
-- Measured Roblox traps this works around: a grounded Humanoid brakes scripted velocity (knockback goes
-- through PlatformStand + Physics state); Motor6D-only rigs need BallSocketConstraints to ragdoll.
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local PhysicsService = game:GetService("PhysicsService")

local HitSystem = {}

-- each character's 5 moves are authored to total ~100, so the bar drains to empty across a character
-- (refilled at each name card) with the ultimate as the big chunk
local MAX_HEALTH = 100
local DAMAGE_COLOURS = {
	{max = 5, color = Color3.fromRGB(255, 255, 255)},
	{max = 12, color = Color3.fromRGB(255, 226, 92)},
	{max = 20, color = Color3.fromRGB(255, 150, 40)},
	{max = math.huge, color = Color3.fromRGB(255, 64, 64)},
}
local ULT_COLOUR = Color3.fromRGB(255, 205, 60)

-- Place a rig so its HumanoidRootPart lands on `at` (facing), then ground it by its FEET: the soles go to
-- at.Y - 3 (a standard R6 root sits 3 studs above the soles). Model:PivotTo alone uses the model's own
-- pivot, which on the imported rigs is not the root, and some rigs (CA Goku) carry the root higher above
-- the legs than a standard R6, so rooting alone still left them waist-deep in the floor.
function HitSystem.placeRoot(model: Model, at: CFrame)
	local root = model:FindFirstChild("HumanoidRootPart") :: BasePart?
	if root then
		model:PivotTo(at * root.CFrame:Inverse() * model:GetPivot())
	else
		model:PivotTo(at)
	end
	local bottom = math.huge
	for _, n in {"Left Leg", "Right Leg"} do
		local leg = model:FindFirstChild(n) :: BasePart?
		if leg then
			bottom = math.min(bottom, leg.Position.Y - leg.Size.Y / 2)
		end
	end
	if bottom < math.huge then
		model:PivotTo(model:GetPivot() + Vector3.new(0, (at.Position.Y - 3) - bottom, 0))
	end
end

local function damageColour(amount: number, ultimate: boolean?): Color3
	if ultimate then
		return ULT_COLOUR
	end
	for _, band in DAMAGE_COLOURS do
		if amount <= band.max then
			return band.color
		end
	end
	return Color3.new(1, 1, 1)
end

-- Overhead health bar: a back plate, a white "recent damage" trail and the live fill.
local function buildHealthBar(target: Model)
	local head = target:FindFirstChild("Head") :: BasePart
	local gui = Instance.new("BillboardGui")
	gui.Name = "HealthBar"
	gui.Size = UDim2.fromOffset(170, 34)
	gui.StudsOffsetWorldSpace = Vector3.new(0, 2.6, 0)
	gui.AlwaysOnTop = true
	gui.LightInfluence = 0
	gui.MaxDistance = 400
	local nameLabel = Instance.new("TextLabel")
	nameLabel.Name = "NameLabel"
	nameLabel.BackgroundTransparency = 1
	nameLabel.Size = UDim2.new(1, 0, 0, 14)
	nameLabel.Font = Enum.Font.GothamBold
	nameLabel.TextSize = 13
	nameLabel.TextColor3 = Color3.new(1, 1, 1)
	nameLabel.TextStrokeTransparency = 0.4
	nameLabel.Text = target.Name
	nameLabel.Parent = gui
	local back = Instance.new("Frame")
	back.Name = "Back"
	back.Position = UDim2.fromOffset(0, 17)
	back.Size = UDim2.new(1, 0, 0, 12)
	back.BackgroundColor3 = Color3.fromRGB(25, 25, 30)
	back.BorderSizePixel = 0
	local corner = Instance.new("UICorner")
	corner.CornerRadius = UDim.new(0, 4)
	corner.Parent = back
	local stroke = Instance.new("UIStroke")
	stroke.Color = Color3.new(0, 0, 0)
	stroke.Thickness = 1.5
	stroke.Parent = back
	back.Parent = gui
	local trail = Instance.new("Frame")
	trail.Name = "Trail"
	trail.Size = UDim2.fromScale(1, 1)
	trail.BackgroundColor3 = Color3.fromRGB(255, 255, 255)
	trail.BorderSizePixel = 0
	corner:Clone().Parent = trail
	trail.Parent = back
	local fill = Instance.new("Frame")
	fill.Name = "Fill"
	fill.Size = UDim2.fromScale(1, 1)
	fill.BackgroundColor3 = Color3.fromRGB(90, 220, 110)
	fill.BorderSizePixel = 0
	corner:Clone().Parent = fill
	fill.Parent = back
	gui.Adornee = head
	gui.Parent = target
end

local function updateHealthBar(target: Model, health: number)
	local gui = target:FindFirstChild("HealthBar")
	if not gui then
		return
	end
	local back = gui:FindFirstChild("Back") :: Frame
	local fill = back:FindFirstChild("Fill") :: Frame
	local trail = back:FindFirstChild("Trail") :: Frame
	local frac = math.clamp(health / MAX_HEALTH, 0, 1)
	-- green -> yellow -> red as health drops
	fill.BackgroundColor3 = frac > 0.5 and Color3.fromRGB(90, 220, 110):Lerp(Color3.fromRGB(240, 210, 60), (1 - frac) * 2)
		or Color3.fromRGB(240, 210, 60):Lerp(Color3.fromRGB(230, 60, 50), (0.5 - frac) * 2)
	fill.Size = UDim2.fromScale(frac, 1)
	-- the white trail catches up after a beat, so each hit's chunk is visible
	task.delay(0.35, function()
		TweenService:Create(trail, TweenInfo.new(0.4, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {Size = UDim2.fromScale(frac, 1)}):Play()
	end)
end

local function popDamageNumber(target: Model, amount: number, ultimate: boolean?)
	local head = target:FindFirstChild("Head") :: BasePart
	local gui = Instance.new("BillboardGui")
	gui.Size = UDim2.fromOffset(160, 60)
	gui.AlwaysOnTop = true
	gui.LightInfluence = 0
	-- scatter a little so a volley of hits does not stack on one spot
	gui.StudsOffsetWorldSpace = Vector3.new((math.random() - 0.5) * 2.4, 1.2 + math.random() * 0.8, 0)
	local label = Instance.new("TextLabel")
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(1, 1)
	label.Font = Enum.Font.FredokaOne
	label.Text = (ultimate and "★ " or "") .. tostring(math.floor(amount + 0.5))
	label.TextColor3 = damageColour(amount, ultimate)
	label.TextScaled = true
	label.TextStrokeTransparency = 0
	label.TextStrokeColor3 = Color3.fromRGB(20, 10, 0)
	local scale = Instance.new("UIScale")
	scale.Scale = 0.2
	scale.Parent = label
	label.Parent = gui
	gui.Adornee = head
	gui.Parent = target
	local big = (ultimate and 1.6) or math.clamp(0.8 + amount / 30, 0.8, 1.4)
	TweenService:Create(scale, TweenInfo.new(0.12, Enum.EasingStyle.Back, Enum.EasingDirection.Out), {Scale = big * 1.25}):Play()
	task.delay(0.12, function()
		TweenService:Create(scale, TweenInfo.new(0.15, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {Scale = big}):Play()
	end)
	local rise = gui.StudsOffsetWorldSpace + Vector3.new(0, 2.2, 0)
	TweenService:Create(gui, TweenInfo.new(0.9, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {StudsOffsetWorldSpace = rise}):Play()
	task.delay(0.55, function()
		TweenService:Create(label, TweenInfo.new(0.35), {TextTransparency = 1, TextStrokeTransparency = 1}):Play()
	end)
	gui:SetAttribute("HitSystemFx", true) -- ours: reset() leaves it to fade out on its own
	task.delay(1, function()
		gui:Destroy()
	end)
end

-- 1-frame white flash, the classic hit read
local function flash(target: Model)
	local hl = Instance.new("Highlight")
	hl.FillColor = Color3.new(1, 1, 1)
	hl.FillTransparency = 0
	hl.OutlineTransparency = 1
	hl.DepthMode = Enum.HighlightDepthMode.Occluded
	hl:SetAttribute("HitSystemFx", true)
	hl.Parent = target
	RunService.RenderStepped:Wait()
	RunService.RenderStepped:Wait()
	hl:Destroy()
end

-- Joints: keep the original Motor6Ds so reset() can put them back exactly
local JOINTS = {"Neck", "Left Shoulder", "Right Shoulder", "Left Hip", "Right Hip"}

local function ragdoll(target: Model)
	local torso = target:FindFirstChild("Torso") :: BasePart
	if target:GetAttribute("Ragdolled") then
		return
	end
	target:SetAttribute("Ragdolled", true)
	for _, name in JOINTS do
		local m = torso:FindFirstChild(name) :: Motor6D?
		if m and m.Part1 then
			local a0 = Instance.new("Attachment")
			a0.Name = "RagA0_" .. name
			a0.CFrame = m.C0
			a0.Parent = m.Part0
			local a1 = Instance.new("Attachment")
			a1.Name = "RagA1_" .. name
			a1.CFrame = m.C1
			a1.Parent = m.Part1
			local bs = Instance.new("BallSocketConstraint")
			bs.Name = "Rag_" .. name
			bs.Attachment0, bs.Attachment1 = a0, a1
			bs.LimitsEnabled = true
			bs.UpperAngle = name == "Neck" and 35 or 70
			bs.TwistLimitsEnabled = true
			bs.TwistLowerAngle, bs.TwistUpperAngle = -40, 40
			bs.Parent = torso
			m.Enabled = false
			local limb = m.Part1 :: BasePart
			limb.CanCollide = true
		end
	end
end

local function unragdoll(target: Model)
	local torso = target:FindFirstChild("Torso") :: BasePart
	for _, d in target:GetDescendants() do
		if d.Name:sub(1, 4) == "Rag_" or d.Name:sub(1, 5) == "RagA0" or d.Name:sub(1, 5) == "RagA1" then
			d:Destroy()
		end
	end
	for _, name in JOINTS do
		local m = torso:FindFirstChild(name) :: Motor6D?
		if m then
			m.Enabled = true
			local limb = m.Part1 :: BasePart?
			if limb then
				limb.CanCollide = false
			end
		end
	end
	target:SetAttribute("Ragdolled", false)
end

-- procedural flinch: snap the torso back on the root joint, ease forward again
local function flinch(target: Model, strength: number)
	local root = target:FindFirstChild("HumanoidRootPart") :: BasePart
	local rj = root:FindFirstChild("RootJoint") :: Motor6D?
	if not rj then
		return
	end
	local t0 = os.clock()
	local conn: RBXScriptConnection
	conn = RunService.RenderStepped:Connect(function()
		local a = (os.clock() - t0) / 0.32
		if a >= 1 or target:GetAttribute("Ragdolled") then
			rj.Transform = CFrame.identity
			conn:Disconnect()
			return
		end
		local k = math.sin(math.min(a * 4, 1) * math.pi / 2) * (1 - a) ^ 2
		rj.Transform = CFrame.Angles(math.rad(-18 * strength * k), math.rad((math.random() - 0.5) * 4 * k), 0)
	end)
end

-- Snapshot of the target as spawned, so reset() can undo kit edits. A plain table: weak tables drop
-- Instance keys.
local PART_PROPS = {"Transparency", "LocalTransparencyModifier", "Color", "Material", "Reflectance", "Size", "CanCollide", "CustomPhysicalProperties", "Massless"}
local DECAL_PROPS = {"Transparency", "LocalTransparencyModifier", "Color3"}
local JOINT_PROPS = {"Enabled", "C0", "C1", "Part0", "Part1"}
local snapshots: {[Model]: {scale: number, items: {[Instance]: {parent: Instance?, props: {[string]: any}}}}} = {}

local function propsFor(inst: Instance): {string}?
	if inst:IsA("BasePart") then
		return PART_PROPS
	elseif inst:IsA("Decal") then -- Texture is a Decal subclass
		return DECAL_PROPS
	elseif inst:IsA("JointInstance") then
		return JOINT_PROPS
	elseif inst:IsA("WeldConstraint") then
		return {"Enabled", "Part0", "Part1"}
	elseif inst:IsA("LayerCollector") then
		return {"Enabled"}
	end
	return nil
end

local function snapshot(target: Model)
	local items = {}
	for _, d in target:GetDescendants() do
		local entry = {parent = d.Parent, props = {}}
		for _, p in propsFor(d) or {} do
			entry.props[p] = (d :: any)[p]
		end
		items[d] = entry
	end
	snapshots[target] = {scale = target:GetScale(), items = items}
end

local function restore(target: Model)
	local snap = snapshots[target]
	if not snap then
		return
	end
	if math.abs(target:GetScale() - snap.scale) > 1e-4 then
		target:ScaleTo(snap.scale)
	end
	-- anything a kit parented under the target goes (HitSystem's own fading popups and flash stay)
	local function isOurFx(inst: Instance): boolean
		local a: Instance? = inst
		while a and a ~= target do
			if a:GetAttribute("HitSystemFx") then
				return true
			end
			a = a.Parent
		end
		return false
	end
	local removed = {}
	for _, d in target:GetDescendants() do
		if not snap.items[d] and d.Parent and not isOurFx(d) then
			table.insert(removed, d.ClassName .. " " .. d.Name)
			d:Destroy()
		end
	end
	if #removed > 0 then
		print("[SHOWCASE] reset removed " .. #removed .. " kit instance(s) from the target: " .. table.concat(removed, ", ", 1, math.min(#removed, 8)))
	end
	for inst, entry in snap.items do
		if inst.Parent ~= entry.parent then
			pcall(function() -- fails only for an instance a kit destroyed
				inst.Parent = entry.parent
			end)
		end
		for p, value in entry.props do
			if (inst :: any)[p] ~= value then
				(inst :: any)[p] = value
			end
		end
	end
end

-- v5f probe: the launched target ploughed into a kit's burst debris (unanchored and colliding on the launch frame)
-- and lost ~40% of its speed. The Director puts every kit part in FX_GROUP and the target lives in TARGET_GROUP;
-- the two never collide, and both still collide with the floor (Default). The groups are registered in the place;
-- this registers them too where the engine allows it.
HitSystem.FX_GROUP, HitSystem.TARGET_GROUP = "ShowcaseFX", "ShowcaseTarget"
function HitSystem.ensureGroups(): boolean
	local fx, tg = HitSystem.FX_GROUP, HitSystem.TARGET_GROUP
	pcall(function()
		for _, g in {fx, tg} do
			if not PhysicsService:IsCollisionGroupRegistered(g) then
				PhysicsService:RegisterCollisionGroup(g)
			end
		end
		PhysicsService:CollisionGroupSetCollidable(fx, tg, false)
	end)
	return PhysicsService:IsCollisionGroupRegistered(fx) and PhysicsService:IsCollisionGroupRegistered(tg)
		and not PhysicsService:CollisionGroupsAreCollidable(fx, tg)
end

function HitSystem.spawnTarget(at: CFrame, name: string?): Model
	local template = ReplicatedStorage:WaitForChild("Showcase"):WaitForChild("TargetRig") :: Model
	local target = template:Clone()
	target.Name = name or "Sparring Partner"
	local hum = target:FindFirstChildOfClass("Humanoid") :: Humanoid
	hum.MaxHealth = MAX_HEALTH
	hum.Health = MAX_HEALTH
	hum.BreakJointsOnDeath = false
	hum.RequiresNeck = false
	hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	hum.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
	HitSystem.placeRoot(target, at)
	local root = target:FindFirstChild("HumanoidRootPart") :: BasePart
	root.Anchored = true
	if HitSystem.ensureGroups() then
		for _, p in target:GetDescendants() do
			if p:IsA("BasePart") then
				p.CollisionGroup = HitSystem.TARGET_GROUP
			end
		end
	else
		warn("[HitSystem] collision groups ShowcaseFX/ShowcaseTarget missing: the target will collide with kit debris")
	end
	target.Parent = workspace
	buildHealthBar(target)
	target:SetAttribute("Health", MAX_HEALTH)
	snapshot(target)
	return target
end

export type HitEvent = {
	damage: number?,
	knock: Vector3?,
	time: number?,
	reaction: string?,
	stun: number?,
	ultimate: boolean?,
	hitstop: number?,
}

-- ============================================================================ v5: the target's physics
-- v5 fix: the target kept getting pushed, then standing upright in the air. It is now thrown as a real
-- body. A small hit on a STANDING target is still a stagger on its feet (anchored slide + flinch); anything
-- bigger ragdolls it (BallSockets) and gives every part one velocity, v0 = knock / T + (0, G T / 2, 0), so it is
-- exactly at start + knock after T (the kits' effects are authored there). Then it keeps flying under gravity G,
-- tumbles AWAY from the hit, bounces, slides on its back and gets up after its stun ("ragdoll" stays down).
-- A hit on an airborne or downed body re-throws it from where it really is (a juggle). The sim (vfxsim.js
-- FOE_PHYS) runs the SAME numbers so the kits are authored against it: keep PHYS in step with it.
local PHYS = {G = 130, SMALL = 2.5, NUDGE = 1.0, NUDGE_UP = 4, SHOVE_T = 0.3, SPIN_K = 0.22, SPIN_MIN = 3, SPIN_MAX = 12,
	GETUP = 0.5, REST_SPEED = 2.0, FRICTION = 0.35, ELASTICITY = 0.3}
type Body = {mode: string, stayDown: boolean, ready: number, face: CFrame, conn: RBXScriptConnection?, upId: number,
	slowSince: number?, toppleAt: number?}
local bodies: {[Model]: Body} = {}

local function body(target: Model): Body
	local b = bodies[target]
	if not b then
		local root = target:FindFirstChild("HumanoidRootPart") :: BasePart
		b = {mode = "stand", stayDown = false, ready = 0, face = root.CFrame - root.CFrame.Position, upId = 0}
		bodies[target] = b
	end
	return b :: Body
end

-- the lift that makes G the target's own gravity (workspace.Gravity stays as it is for everything else),
-- the surface it slides on, and limbs that do not fight the torso they hang from
local function addPhysics(target: Model)
	local g = workspace.Gravity
	for _, p in target:GetDescendants() do
		-- every part gets the lift, the root too: it rides the torso's assembly and is 2.8 of the body's 12.6 mass,
		-- and without its share the body fell at ~145 instead of G (v5e: Spirit Bomb's launch peaked at 20, not ~37)
		if p:IsA("BasePart") then
			if p.Name ~= "HumanoidRootPart" then
				p.CustomPhysicalProperties = PhysicalProperties.new(0.7, PHYS.FRICTION, PHYS.ELASTICITY, 1, 1)
			end
			local a = Instance.new("Attachment")
			a.Name = "PhysA"
			a:SetAttribute("HitPhys", true)
			a.Parent = p
			local f = Instance.new("VectorForce")
			f.Name = "PhysLift"
			f:SetAttribute("HitPhys", true)
			f.Attachment0 = a
			f.ApplyAtCenterOfMass = true
			f.RelativeTo = Enum.ActuatorRelativeTo.World
			f.Force = Vector3.new(0, p:GetMass() * (g - PHYS.G), 0)
			f.Parent = p
		end
	end
	local torso = target:FindFirstChild("Torso") :: BasePart
	for _, n in {"Head", "Left Arm", "Right Arm", "Left Leg", "Right Leg"} do
		local limb = target:FindFirstChild(n) :: BasePart?
		if limb then
			local nc = Instance.new("NoCollisionConstraint")
			nc.Name = "PhysNoCollide"
			nc:SetAttribute("HitPhys", true)
			nc.Part0, nc.Part1 = torso, limb
			nc.Parent = torso
		end
	end
end

local function removePhysics(target: Model)
	for _, d in target:GetDescendants() do
		if d:GetAttribute("HitPhys") then
			d:Destroy()
		end
	end
end

local function throw(target: Model, v: Vector3, w: Vector3)
	local torso = target:FindFirstChild("Torso") :: BasePart
	local c = torso.Position
	for _, p in target:GetDescendants() do
		if p:IsA("BasePart") then
			p.AssemblyLinearVelocity = v + w:Cross(p.Position - c)
			p.AssemblyAngularVelocity = w
		end
	end
end

local function goLimp(target: Model)
	local hum = target:FindFirstChildOfClass("Humanoid") :: Humanoid
	local root = target:FindFirstChild("HumanoidRootPart") :: BasePart
	ragdoll(target)
	addPhysics(target)
	hum.PlatformStand = true
	-- v5c probe: with the state machine switched off in a standing state the Humanoid kept balancing the body
	-- upright (Kurohitsugi's finisher hopped it 2.5 studs without tipping). Physics = no Humanoid forces at all.
	hum:ChangeState(Enum.HumanoidStateType.Physics)
	hum.EvaluateStateMachine = false
	root.Anchored = false
end

local function floorY(target: Model, at: Vector3): number
	-- the arena floor, then terrain only where there is no arena: a kit's debris under the body made the get-up stand
	-- 0.37 studs in the air (v5c), and the terrain under the ring pokes through it by up to ~0.13 (v5d)
	local params = RaycastParams.new()
	local arena = workspace:FindFirstChild("Arena")
	local from, dir = at + Vector3.new(0, 4, 0), Vector3.new(0, -60, 0)
	if arena then
		params.FilterType = Enum.RaycastFilterType.Include
		params.FilterDescendantsInstances = {arena}
		local hit = workspace:Raycast(from, dir, params)
		if hit then
			return hit.Position.Y
		end
		params.FilterDescendantsInstances = {workspace.Terrain}
	else
		params.FilterType = Enum.RaycastFilterType.Exclude
		params.FilterDescendantsInstances = {target}
	end
	local hit = workspace:Raycast(from, dir, params)
	return hit and hit.Position.Y or 0
end

-- the rig's parts as boxes in ROOT space at rest (from the joints, so it holds for any R6 rig and head mesh), and how
-- far below the root the straight (rejoined) body's lowest corner sits for a rotation R: the get-up's floor contact
type Box = {rel: CFrame, half: Vector3}
local function bodyBoxes(target: Model): {Box}
	local root = target:FindFirstChild("HumanoidRootPart") :: BasePart
	local torso = target:FindFirstChild("Torso") :: BasePart
	local rj = root:FindFirstChild("RootJoint") :: Motor6D?
	local torsoRel = if rj then rj.C0 * rj.C1:Inverse() else CFrame.identity
	local boxes: {Box} = {{rel = torsoRel, half = torso.Size / 2}}
	for _, name in JOINTS do
		local m = torso:FindFirstChild(name) :: Motor6D?
		if m and m.Part1 then
			table.insert(boxes, {rel = torsoRel * m.C0 * m.C1:Inverse(), half = (m.Part1 :: BasePart).Size / 2})
		end
	end
	return boxes
end

local function clearance(boxes: {Box}, R: CFrame): number
	local low = math.huge
	for _, b in boxes do
		local c = R * b.rel
		local h = b.half
		low = math.min(low, c.Position.Y - (math.abs(c.RightVector.Y) * h.X + math.abs(c.UpVector.Y) * h.Y + math.abs(c.LookVector.Y) * h.Z))
	end
	return -low
end

local function getUp(target: Model)
	local b = body(target)
	local hum = target:FindFirstChildOfClass("Humanoid") :: Humanoid
	local root = target:FindFirstChild("HumanoidRootPart") :: BasePart
	local torso = target:FindFirstChild("Torso") :: BasePart
	local from = torso.CFrame -- the visible body (the ragdolled root can drift); in R6 they coincide once rejoined
	local at = torso.Position
	removePhysics(target)
	unragdoll(target)
	for _, p in target:GetDescendants() do
		if p:IsA("BasePart") then
			p.AssemblyLinearVelocity = Vector3.zero
			p.AssemblyAngularVelocity = Vector3.zero
		end
	end
	root.Anchored = true
	-- the first frame is placed BEFORE the first Heartbeat: the rejoined (straight) limbs at the ragdoll's pose dipped
	-- 0.2-0.34 under the floor for one sample (v5 take: sasuke1, dio1, law3, kakashi5)
	root.CFrame = CFrame.new(from.X, floorY(target, at) + clearance(bodyBoxes(target), from.Rotation), from.Z) * from.Rotation
	hum.EvaluateStateMachine = true
	b.mode = "getup"
	b.toppleAt = nil
	b.slowSince = nil
	b.upId += 1
	local id = b.upId
	-- v5 probe: tweening the root CFrame swung the legs ~0.9 studs through the floor. The body now TIPS UP OVER
	-- ITS FEET (a tilt in the vertical plane, so nothing dips under the floor), then turns to its facing.
	-- vfxsim.js getUpPlan does the same.
	local R0 = from.Rotation
	local u0 = R0.UpVector
	local axis = u0:Cross(Vector3.yAxis)
	axis = if axis.Magnitude < 1e-3 then Vector3.xAxis else axis.Unit
	local ang = math.acos(math.clamp(u0.Y, -1, 1))
	-- every frame the root sits exactly so the straight body's LOWEST CORNER is on the floor, so nothing sinks or
	-- hovers from any start (v5c-v5g probes: a sitting body sank 1.3; a head-down one, whose ragdolled legs bent at
	-- the hips, put its "feet" 0.7 up in the air and floated up to 0.68). Horizontally it tips up over its feet.
	local base = from.Position - u0 * 3
	local fy = floorY(target, at)
	local boxes = bodyBoxes(target)
	local l1 = (CFrame.fromAxisAngle(axis, ang) * R0).LookVector
	local l2 = b.face.LookVector
	local yaw = math.atan2(l1.Z * l2.X - l1.X * l2.Z, l1.X * l2.X + l1.Z * l2.Z)
	local t0 = os.clock()
	local conn: RBXScriptConnection
	conn = RunService.Heartbeat:Connect(function()
		if b.mode ~= "getup" or b.upId ~= id or not target.Parent then
			conn:Disconnect()
			return
		end
		local a = math.min(1, (os.clock() - t0) / PHYS.GETUP)
		local q = 1 - (1 - a) * (1 - a)
		if a >= 1 then
			conn:Disconnect()
			root.CFrame = CFrame.new(Vector3.new(base.X, fy + 3, base.Z)) * b.face
			b.mode = "stand"
			return
		end
		local R = CFrame.fromAxisAngle(Vector3.yAxis, yaw * q) * CFrame.fromAxisAngle(axis, ang * q) * R0
		local up = R.UpVector
		root.CFrame = CFrame.new(base.X + up.X * 3, fy + clearance(boxes, R), base.Z + up.Z * 3) * R
	end)
end

-- one watcher per target: a thrown body that has come to rest gets up once its stun is over
local function watch(target: Model)
	local b = body(target)
	if b.conn then
		return
	end
	local torso = target:FindFirstChild("Torso") :: BasePart
	b.conn = RunService.Heartbeat:Connect(function()
		if not target.Parent then
			if b.conn then
				b.conn:Disconnect()
			end
			bodies[target] = nil
			return
		end
		if b.mode ~= "air" then
			return
		end
		-- at rest = slow for a quarter second (v5c: a body that landed ON ITS FEET never read as resting by height)
		local now = os.clock()
		-- an UPRIGHT body (sitting, leaning) creeps as it slumps, so it counts as at rest below 5 studs/s held for 0.4 s
		-- (v5f: under 2 it took Kurohitsugi's half-sitting target 2.1 s to read as resting)
		local upright = torso.CFrame.UpVector.Y > 0.35
		if torso.AssemblyLinearVelocity.Magnitude < (if upright then 5 else PHYS.REST_SPEED) then
			b.slowSince = b.slowSince or now
		else
			b.slowSince = nil
		end
		local resting = b.slowSince ~= nil and now - (b.slowSince :: number) >= (if upright then 0.4 else 0.25)
		if resting and not b.stayDown and now >= b.ready then
			if torso.CFrame.UpVector.Y > 0.35 and not b.toppleAt then
				-- still on its feet or half sitting: it falls onto its back first, then gets up from lying
				b.toppleAt = now
				b.slowSince = nil
				b.ready = now + 0.3
				local back = -Vector3.new(b.face.LookVector.X, 0, b.face.LookVector.Z).Unit
				local lean = Vector3.new(torso.CFrame.UpVector.X, 0, torso.CFrame.UpVector.Z)
				local dir = if lean.Magnitude > 0.2 then lean.Unit else back
				-- a DRIVEN topple: one spin push did not tip a half-sitting body (v5e). An AngularVelocity holds the torso
				-- rolling over for 0.4 s while the limbs stay ragdolled
				throw(target, dir * 3 + Vector3.new(0, 2, 0), Vector3.yAxis:Cross(dir) * 6)
				local att = torso:FindFirstChild("PhysA") :: Attachment?
				if att then
					local av = Instance.new("AngularVelocity")
					av.Name = "PhysTopple"
					av:SetAttribute("HitPhys", true)
					av.Attachment0 = att
					av.RelativeTo = Enum.ActuatorRelativeTo.World
					av.AngularVelocity = Vector3.yAxis:Cross(dir) * 6
					av.MaxTorque = 1e5
					av.Parent = torso
					task.delay(0.4, function()
						av:Destroy()
					end)
				end
			elseif torso.CFrame.UpVector.Y <= 0.35 or now - (b.toppleAt :: number) > 1.2 then
				getUp(target)
			end
		end
	end)
end

-- v5 probe: a body still down when its move ends gets up ON SCREEN (the Director waits on isStanding) instead of
-- lying there until reset() snaps it upright behind the next title card
function HitSystem.recover(target: Model)
	local b = bodies[target]
	if b and b.mode ~= "stand" then
		b.stayDown = false
		b.ready = 0
	end
end

function HitSystem.isStanding(target: Model): boolean
	local b = bodies[target]
	return b == nil or b.mode == "stand"
end

function HitSystem.Hit(target: Model, ev: HitEvent)
	if not target or not target.Parent then
		return
	end
	local hum = target:FindFirstChildOfClass("Humanoid") :: Humanoid
	local root = target:FindFirstChild("HumanoidRootPart") :: BasePart
	local damage = ev.damage or 0
	local reaction = ev.reaction or "flinch"
	-- the showcase never kills: health floors at 1 so every move plays on a standing target until reset
	local health = math.max((target:GetAttribute("Health") :: number) - damage, 1)
	target:SetAttribute("Health", health)
	hum.Health = health
	updateHealthBar(target, health)
	if damage > 0 then
		popDamageNumber(target, damage, ev.ultimate)
	end
	task.spawn(flash, target)

	local b = body(target)
	watch(target)
	local d = ev.knock or Vector3.zero
	local T = math.clamp(ev.time or 0.22, 0.02, 2)
	local mag = d.Magnitude
	local stun = ev.stun or ({flinch = 0.3, knockback = 0.5, launch = 0.8, ragdoll = 1.5})[reaction] or 0.4
	local function applyMotion()
		b.ready = math.max(b.ready, os.clock() + T + stun)
		if reaction == "ragdoll" then
			b.stayDown = true
		end
		if reaction == "warp" then
			-- a teleport (Law's Shambles): the target is simply THERE, standing, facing as before
			removePhysics(target)
			unragdoll(target)
			root.Anchored = true
			hum.EvaluateStateMachine = true
			local torso = target:FindFirstChild("Torso") :: BasePart
			local at = (b.mode == "stand") and root.Position or Vector3.new(torso.Position.X, root.Position.Y, torso.Position.Z)
			root.CFrame = CFrame.new(at + d) * b.face
			b.mode = "stand"
			return
		end
		if b.mode == "stand" and mag <= PHYS.SMALL and (reaction == "flinch" or reaction == "knockback") then
			-- a stagger on its feet: an anchored slide plus the flinch
			root.Anchored = true
			flinch(target, math.clamp(damage / 25, 0.5, 1.4) * (reaction == "knockback" and 1.3 or 1))
			-- never down through the floor: Bajrang Gun's -2.6 of presses buried the target to the waist (v5 take)
			local floor = floorY(target, root.Position) + 3
			if root.Position.Y + d.Y < floor then
				d = Vector3.new(d.X, math.min(0, floor - root.Position.Y), d.Z)
				mag = d.Magnitude
			end
			if mag > 0 then
				TweenService:Create(root, TweenInfo.new(T, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {CFrame = root.CFrame + d}):Play()
			end
			return
		end
		local airborne = b.mode ~= "stand"
		if b.mode == "stand" or b.mode == "getup" then
			goLimp(target)
		end
		local torso = target:FindFirstChild("Torso") :: BasePart
		local v: Vector3
		if airborne and mag <= PHYS.NUDGE then
			v = torso.AssemblyLinearVelocity + d * (0.6 / T) + Vector3.new(0, PHYS.NUDGE_UP, 0)
		else
			local Tt = reaction == "knockback" and math.max(T, PHYS.SHOVE_T) or T
			v = d / Tt + Vector3.new(0, 0.5 * PHYS.G * Tt, 0)
		end
		local flat = Vector3.new(v.X, 0, v.Z)
		local dir = flat.Magnitude > 1e-3 and flat.Unit or Vector3.new(0, 0, -1)
		local axis = Vector3.yAxis:Cross(dir) -- the top goes WITH the hit: it falls away from it
		local spin = math.clamp(v.Magnitude * PHYS.SPIN_K, PHYS.SPIN_MIN, PHYS.SPIN_MAX) * (reaction == "ragdoll" and 1.3 or 1)
		local w = if airborne and mag <= PHYS.NUDGE then torso.AssemblyAngularVelocity + axis * 1.5 else axis * spin
		b.mode = "air"
		b.toppleAt = nil
		b.slowSince = nil
		throw(target, v, w)
	end
	if (ev.hitstop or 0) > 0 then
		task.delay(ev.hitstop :: number, applyMotion)
	else
		applyMotion()
	end
end

-- refill = true only at a character's name card; between moves the health carries over (it drains
-- across the character's five moves)
-- refill: true = full health; a number = set health to it (a single-move re-record matching the take's health)
function HitSystem.reset(target: Model, at: CFrame, refill: (boolean | number)?)
	local hum = target:FindFirstChildOfClass("Humanoid") :: Humanoid
	local root = target:FindFirstChild("HumanoidRootPart") :: BasePart
	removePhysics(target)
	unragdoll(target)
	hum.EvaluateStateMachine = true
	restore(target) -- undo kit edits (scale, hidden or recoloured parts, disabled joints, added instances)
	for _, p in target:GetDescendants() do
		if p:IsA("BasePart") then
			p.AssemblyLinearVelocity = Vector3.zero
			p.AssemblyAngularVelocity = Vector3.zero
		end
	end
	target:SetAttribute("StunToken", (target:GetAttribute("StunToken") or 0) + 1)
	root.Anchored = true
	HitSystem.placeRoot(target, at)
	hum.PlatformStand = false
	local b = body(target)
	b.mode, b.stayDown, b.ready = "stand", false, 0
	b.face = at - at.Position -- it faces the caster from here
	if refill then
		local health = type(refill) == "number" and refill or MAX_HEALTH
		hum.Health = health
		target:SetAttribute("Health", health)
		updateHealthBar(target, health)
		local bar = target:FindFirstChild("HealthBar") :: BillboardGui
		local trail = bar:FindFirstChild("Back"):FindFirstChild("Trail") :: Frame
		trail.Size = UDim2.fromScale(health / MAX_HEALTH, 1)
	end
	-- it stands anchored between moves; physics takes it over on its first real hit
	hum:ChangeState(Enum.HumanoidStateType.GettingUp)
end

HitSystem.MAX_HEALTH = MAX_HEALTH
return HitSystem
