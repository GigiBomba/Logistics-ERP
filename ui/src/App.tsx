import { Routes, Route } from "react-router-dom"
import { AppShell } from "@/components/layout/app-shell"
import HomePage from "@/pages/home"
import AboutPage from "@/pages/public/about"
import DownloadPage from "@/pages/public/download"
import MissionPage from "@/pages/public/mission"
import NotFoundPage from "@/pages/not-found"

function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/download" element={<DownloadPage />} />
        <Route path="/mission" element={<MissionPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}

export default App
