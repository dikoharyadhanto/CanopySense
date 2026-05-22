import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../lib/api';

export default function Dashboard() {
  const navigate = useNavigate();
  const [blocks, setBlocks] = useState<any[]>([]);

  useEffect(() => {
    if (!localStorage.getItem('token')) {
      navigate('/login');
      return;
    }

    const fetchBlocks = async () => {
      try {
        const res = await api.get('/api/blocks');
        setBlocks(res.data);
      } catch (err) {
        console.warn("Failed to fetch blocks, using mock data");
        setBlocks([
          { id: 1, name: "Block 1", code: "BLK-001", afdeling_name: "Afdeling 1", estate_name: "Estate Alpha" },
          { id: 2, name: "Block 2", code: "BLK-002", afdeling_name: "Afdeling 1", estate_name: "Estate Alpha" }
        ]);
      }
    };
    fetchBlocks();
  }, [navigate]);

  return (
    <div className="flex h-screen overflow-hidden bg-gray-100">
      <aside className="w-64 bg-white border-r shadow-sm overflow-y-auto">
        <div className="p-4 border-b">
          <h2 className="text-xl font-bold text-green-700">CanopySense</h2>
        </div>
        <nav className="p-4">
          <div className="font-semibold text-gray-600 mb-2">Company / Estate</div>
          <ul className="space-y-2">
            <li className="px-3 py-2 bg-green-50 text-green-700 rounded-md cursor-pointer font-medium">
              Estate Alpha
            </li>
          </ul>
          
          <div className="font-semibold text-gray-600 mb-2 mt-6">Blocks</div>
          <ul className="space-y-2">
            {blocks.map((b: any) => (
              <li key={b.id} className="px-3 py-2 hover:bg-gray-50 rounded-md cursor-pointer text-sm text-gray-700">
                {b.name} ({b.code})
              </li>
            ))}
          </ul>
        </nav>
      </aside>
      
      <main className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b px-6 py-4 flex justify-between items-center shadow-sm">
          <h1 className="text-2xl font-semibold text-gray-800">Estate Map View</h1>
          <button 
            onClick={() => { localStorage.removeItem('token'); navigate('/login'); }}
            className="text-sm font-medium text-red-600 hover:text-red-800"
          >
            Logout
          </button>
        </header>
        <div className="flex-1 p-6 overflow-auto">
          <div className="bg-white rounded-lg shadow-sm border p-4 h-full flex flex-col items-center justify-center">
            <div className="text-gray-400 mb-4">
              <svg className="w-16 h-16 mx-auto" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-900">Map View Placeholder</h3>
            <p className="text-gray-500 text-sm mt-1">Leaflet map component goes here</p>
          </div>
        </div>
      </main>
    </div>
  );
}
