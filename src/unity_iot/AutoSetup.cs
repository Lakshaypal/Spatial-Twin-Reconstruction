using UnityEngine;
using UnityEditor;

[InitializeOnLoad]
public class AutoSetup
{
    static AutoSetup()
    {
        EditorApplication.delayCall += RunSetup;
    }

    static void RunSetup()
    {
        // Ensure this only runs once per session
        if (SessionState.GetBool("AutoSetupDone", false)) return;
        SessionState.SetBool("AutoSetupDone", true);

        // Hide gray mesh renderer on the collision mesh
        GameObject untitled = GameObject.Find("Untitled");
        if (untitled != null)
        {
            MeshRenderer mr = untitled.GetComponent<MeshRenderer>();
            if (mr != null)
            {
                mr.enabled = false;
                Debug.Log("Disabled MeshRenderer on 'Untitled' object for collision-only physics.");
            }
        }
        
        // Find or create Agent Spawner
        if (GameObject.Find("Spawner") == null)
        {
            GameObject spawner = new GameObject("Spawner");
            
            // Try to add the AgentSpawner script via reflection
            System.Type spawnerType = System.Type.GetType("AgentSpawner, Assembly-CSharp");
            if (spawnerType != null)
            {
                spawner.AddComponent(spawnerType);
                Debug.Log("Created Spawner object and attached AgentSpawner script.");
            }
            else
            {
                Debug.LogWarning("Could not automatically attach AgentSpawner script. Please attach it manually to the Spawner object.");
            }
        }
        
        Debug.Log("Auto Setup Completed! The Pcx package has been installed automatically. You can now drag your mesh_lingbot asset into the scene!");
    }
}