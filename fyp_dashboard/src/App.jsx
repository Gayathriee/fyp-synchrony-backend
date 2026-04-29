import { useState, useEffect, useRef } from 'react'

function App() {
  const [status, setStatus] = useState("Connecting...");
  const [aiIntervention, setAiIntervention] = useState(null);
  const [teamStats, setTeamStats] = useState({
    1: { stress: "Waiting...", rmssd: 0 },
    2: { stress: "Waiting...", rmssd: 0 },
    3: { stress: "Waiting...", rmssd: 0 }
  });
  
  const socket = useRef(null);

  useEffect(() => {
    const connect = () => {
      socket.current = new WebSocket("ws://127.0.0.1:8000/ws");

      socket.current.onopen = () => setStatus("✅ System Online");
      
      socket.current.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "live_stats") {
          setTeamStats(prev => ({
            ...prev,
            [data.participant_id]: { stress: data.stress, rmssd: data.rmssd }
          }));
        }
        if (data.type === "intervention") {
          setAiIntervention(data.message);
          setTimeout(() => setAiIntervention(null), 15000);
        }
      };

      socket.current.onclose = () => {
        setStatus("❌ Reconnecting...");
        setTimeout(connect, 2000); // Attempt to reconnect every 2 seconds
      };
    };

    connect();
    return () => socket.current?.close();
  }, []);

  return (
    <div style={{ padding: '40px', fontFamily: 'sans-serif', backgroundColor: '#f4f7f6', minHeight: '100vh' }}>
      <div style={{ maxWidth: '900px', margin: '0 auto', textAlign: 'center' }}>
        <h1 style={{ color: '#2c3e50' }}>🧠 Hybrid AI Research Dashboard</h1>
        <p style={{ fontWeight: 'bold', color: status.includes('✅') ? '#27ae60' : '#e74c3c' }}>{status}</p>

        <div style={{ display: 'flex', gap: '20px', justifyContent: 'center', margin: '40px 0' }}>
          {[1, 2, 3].map(id => (
            <div key={id} style={{ backgroundColor: 'white', padding: '25px', borderRadius: '15px', boxShadow: '0 4px 15px rgba(0,0,0,0.05)', flex: 1 }}>
              <h3 style={{ margin: 0, color: '#7f8c8d' }}>P{id}</h3>
              <p style={{ fontSize: '24px', fontWeight: 'bold', color: '#2c3e50' }}>{teamStats[id].stress}</p>
              <div style={{ color: '#3498db', fontWeight: 'bold' }}>{teamStats[id].rmssd} ms</div>
            </div>
          ))}
        </div>

        {aiIntervention && (
          <div style={{ backgroundColor: '#fffbe6', border: '2px solid #ffe58f', padding: '30px', borderRadius: '15px', animation: 'pulse 2s infinite' }}>
            <h2 style={{ color: '#d4a017', margin: '0 0 10px 0' }}>🤖 AI AGENT</h2>
            <p style={{ fontSize: '22px', fontStyle: 'italic', margin: 0 }}>"{aiIntervention}"</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default App;