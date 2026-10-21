using UnityEngine;
using System.Text;
using uPLibrary.Networking.M2Mqtt;
using uPLibrary.Networking.M2Mqtt.Messages;
using TMPro;

public class MqttIoTReceiver : MonoBehaviour
{
    public string brokerAddress = "127.0.0.1";
    public int brokerPort = 1883;
    public string topic = "sensor/dht11";

    private MqttClient client;
    private TextMeshPro textMesh;
    private string lastMessage = "Waiting for data...";

    void Start()
    {
        textMesh = GetComponent<TextMeshPro>();
        if (textMesh == null)
        {
            Debug.LogError("MqttIoTReceiver requires a TextMeshPro component!");
            return;
        }

        try
        {
            client = new MqttClient(brokerAddress, brokerPort, false, null, null, MqttSslProtocols.None);
            string clientId = System.Guid.NewGuid().ToString();
            
            client.MqttMsgPublishReceived += client_MqttMsgPublishReceived;
            client.Connect(clientId);
            
            client.Subscribe(new string[] { topic }, new byte[] { MqttMsgBase.QOS_LEVEL_EXACTLY_ONCE });
            
            Debug.Log("Connected to MQTT broker at " + brokerAddress);
        }
        catch (System.Exception e)
        {
            Debug.LogError("Error connecting to MQTT Broker: " + e.Message);
        }
    }

    void client_MqttMsgPublishReceived(object sender, MqttMsgPublishEventArgs e)
    {
        // Handle message reception on background thread
        lastMessage = Encoding.UTF8.GetString(e.Message);
    }

    void Update()
    {
        // Update UI on main Unity thread
        if (textMesh != null)
        {
            textMesh.text = "IoT Sensor Data\n" + lastMessage;
        }
    }

    void OnApplicationQuit()
    {
        if (client != null && client.IsConnected)
        {
            client.Disconnect();
        }
    }
}
