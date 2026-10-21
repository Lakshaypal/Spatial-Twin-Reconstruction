using UnityEngine;
using UnityEditor;

public class FixScene
{
    [MenuItem("Tools/Import Phase 2 Mesh (Solid Walls)")]
    public static void ImportPhase2Mesh()
    {
        // Remove old point cloud objects
        GameObject oldPc = GameObject.Find("MeshLingbot_Colors");
        if (oldPc != null) Object.DestroyImmediate(oldPc);

        GameObject oldMesh = GameObject.Find("mesh_lingbot");
        if (oldMesh != null) Object.DestroyImmediate(oldMesh);

        // Load the Phase 2 textured OBJ (MeshSplatting from COLMAP poses)
        GameObject meshPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(
            "Assets/mesh_splatting_pano_textured.obj");

        if (meshPrefab != null)
        {
            GameObject instance = (GameObject)PrefabUtility.InstantiatePrefab(meshPrefab);
            instance.name = "DigitalTwin_Phase2";
            instance.transform.position = Vector3.zero;
            instance.transform.rotation = Quaternion.identity;

            // Ensure it has a MeshCollider for physics
            MeshFilter mf = instance.GetComponentInChildren<MeshFilter>();
            if (mf != null)
            {
                MeshCollider mc = mf.gameObject.GetComponent<MeshCollider>();
                if (mc == null)
                    mc = mf.gameObject.AddComponent<MeshCollider>();
            }

            Debug.Log("Imported Phase 2 mesh (375k vertices, 224k faces) as solid textured geometry!");
        }
        else
        {
            Debug.LogError("Could not find Assets/mesh_splatting_pano_textured.obj! " +
                           "Run bake_texture.py first.");
        }

        // Fix camera
        Camera cam = Camera.main;
        if (cam != null)
        {
            cam.transform.position = new Vector3(5, 5, -15);
            cam.transform.LookAt(Vector3.zero);
            cam.farClipPlane = 500f;
            Debug.Log("Camera repositioned.");
        }
    }

    [MenuItem("Tools/Fix Camera And Colors")]
    public static void FixIt()
    {
        Camera cam = Camera.main;
        if (cam != null)
        {
            cam.transform.position = new Vector3(5, 5, -15);
            cam.transform.LookAt(Vector3.zero);
            Debug.Log("Moved Main Camera to face the scene.");
        }
    }
}
