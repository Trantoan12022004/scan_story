import React, { useState, useEffect } from 'react'
import { Sidebar, NavTab } from './components/Sidebar'
import { QuanLyPage } from './pages/QuanLyPage'
import { TaiReelsPage } from './pages/TaiReelsPage'
import { CaoTruyenPage } from './pages/CaoTruyenPage'
import { GeminiPage } from './pages/GeminiPage'
import { CaiDatPage } from './pages/CaiDatPage'
import { BanQuyenPage } from './pages/BanQuyenPage'

export function App(): React.JSX.Element {
  const [currentTab, setCurrentTab] = useState<NavTab>('quan_ly')
  const [totalVideos, setTotalVideos] = useState<number>(0)

  useEffect(() => {
    const fetchTotal = async () => {
      try {
        const stats = await window.api.db.getStatCounts()
        setTotalVideos(stats?.total || 0)
      } catch { }
    }
    fetchTotal()
  }, [currentTab])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50 text-slate-800 antialiased font-sans select-none">
      {/* Left Modern Sidebar */}
      <Sidebar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        totalVideos={totalVideos}
      />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full overflow-hidden bg-slate-50">
        {currentTab === 'quan_ly' && <QuanLyPage />}
        {currentTab === 'tai_reels' && <TaiReelsPage />}
        {currentTab === 'cao_truyen' && <CaoTruyenPage />}
        {currentTab === 'gemini' && <GeminiPage />}
        {currentTab === 'cai_dat' && <CaiDatPage />}
        {currentTab === 'ban_quyen' && <BanQuyenPage />}
      </main>
    </div>
  )
}

export default App
