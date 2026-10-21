# Unity Deployment Guide (Phase 5)

This guide walks you through importing your digital twin into Unity, baking a NavMesh for AI agents, setting up the crowd simulation, and receiving live IoT data via MQTT.

## 1. Project Setup
1. Open **Unity Hub** and create a new **3D (URP or Standard)** project.
2. Drag and drop the `mesh_lingbot.ply` (or `master_mesh.ply`) file into your Unity `Assets/` folder to import it.
   - *Note: Unity supports PLY files natively in newer versions, but if your version doesn't, you may need a PLY importer plugin (like Keijiro's Pcx), or you can open the mesh in Blender and export it as an `.obj` or `.fbx`.*
3. Drag the mesh from the Project window into your Scene Hierarchy.
4. **Important:** Add a `Mesh Collider` component to the mesh object so that rays and physics can interact with the walls.

## 2. NavMesh & Proxy Planes
Raw scanned meshes are very bumpy. If you bake a NavMesh directly onto it, the AI agents will get stuck on tiny jagged edges on the floor. 

1. Create a **3D Object -> Plane** in Unity.
2. Scale and position the plane so it perfectly covers the walkable floor area of your digital twin mesh.
3. In the Plane's Inspector, remove its `Mesh Renderer` (so it becomes invisible).
4. Go to **Window -> AI -> Navigation**.
5. Select your invisible Plane, check **Navigation Static**, and set it to **Walkable**.
6. Make sure your scanned digital twin mesh is **NOT** marked as Walkable.
7. Go to the **Bake** tab in the Navigation window and click **Bake**. You should see a blue overlay representing the walkable area on your floor plane!

## 3. Crowd Simulation
1. Copy the runtime `.cs` files from `src/unity_iot/` into your Unity `Assets/Scripts/` folder. Place `AutoSetup.cs` and `FixScene.cs`, which use `UnityEditor`, under `Assets/Editor/`.
2. Create a generic 3D capsule to act as your crowd agent (**GameObject -> 3D Object -> Capsule**). 
3. Add a **NavMesh Agent** component to the capsule.
4. Attach the `CrowdAgent.cs` script to the capsule.
5. Drag this capsule into your Project window to create a **Prefab**, then delete it from the scene.
6. Create an empty GameObject in your scene named `Spawner`.
7. Attach the `AgentSpawner.cs` script to `Spawner`, and drag your Capsule Prefab into the "Agent Prefab" slot in the script's inspector. Set `NumberOfAgents` to 10.
8. Hit **Play**! You will see 10 agents spawn and wander randomly around the digital twin's floor.

## 4. IoT Integration (MQTT)
To get live Arduino data (like DHT11 temperature/humidity) onto the walls of the digital twin:
1. You need the **M2Mqtt** library. You can download the `M2Mqtt.dll` from GitHub and place it in your `Assets/Plugins` folder in Unity.
2. Create a **3D Object -> 3D Text (TextMeshPro)** in your scene. Position it on the wall of the digital twin where the physical Arduino is located.
3. Attach the `MqttIoTReceiver.cs` script to this Text object.
4. In the script's inspector, set the `Broker Address` to `127.0.0.1` (or the IP of your Raspberry Pi / server running Mosquitto).
5. Open a terminal and start your local Mosquitto broker if it's installed: `mosquitto -v`
6. Run the provided Python simulator to fake Arduino data: `python src/unity_iot/arduino_simulator.py`
7. Hit **Play** in Unity. You will see the 3D text on the wall update in real-time with the simulated temperature and humidity data!