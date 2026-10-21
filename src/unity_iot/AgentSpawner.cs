using UnityEngine;
using UnityEngine.AI;

public class AgentSpawner : MonoBehaviour
{
    public GameObject agentPrefab;
    public int numberOfAgents = 10;
    public float spawnRadius = 10f;

    void Start()
    {
        SpawnAgents();
    }

    void SpawnAgents()
    {
        for (int i = 0; i < numberOfAgents; i++)
        {
            Vector3 spawnPoint = GetRandomPointOnNavMesh();
            if (spawnPoint != Vector3.zero)
            {
        int spawnedCount = 0;
        while (spawnedCount < numberOfAgents)
        {
            if (agentPrefab == null)
            {
#if UNITY_EDITOR
                agentPrefab = UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>("Assets/AgentPrefab.prefab");
#endif
                if (agentPrefab == null) return;
            }

            Vector3 randomPoint = transform.position + Random.insideUnitSphere * spawnRadius;
            NavMeshHit hit;
            if (NavMesh.SamplePosition(randomPoint, out hit, spawnRadius, NavMesh.AllAreas))
            {
                Instantiate(agentPrefab, hit.position, Quaternion.identity);
                spawnedCount++;
            }
        }
    }

    Vector3 GetRandomPointOnNavMesh()
    {
        Vector3 randomDirection = Random.insideUnitSphere * spawnRadius;
        randomDirection += transform.position;
        
        NavMeshHit hit;
        if (NavMesh.SamplePosition(randomDirection, out hit, spawnRadius, NavMesh.AllAreas))
        {
            return hit.position;
        }
        
        return Vector3.zero;
    }
}
