import { Navigate, Route, Routes } from 'react-router-dom';
import { ProtectedRoute, PublicOnlyRoute } from './auth/routes.jsx';
import AppLayout from './layouts/AppLayout.jsx';
import Entry from './pages/Entry.jsx';
import Login from './pages/Login.jsx';
import Register from './pages/Register.jsx';
import Emergency from './pages/Emergency.jsx';
import Home from './pages/Home.jsx';
import Family from './pages/Family.jsx';
import { Documents, Knowledge } from './pages/Collections.jsx';
import Settings from './pages/Settings.jsx';
import Health from './pages/Health.jsx';
import DocumentDetail from './pages/DocumentDetail.jsx';
import Medicines from './pages/Medicines.jsx';
import Diet from './pages/Diet.jsx';
import Wellness from './pages/Wellness.jsx';
import Timeline from './pages/Timeline.jsx';
import Reminders from './pages/Reminders.jsx';
import Sharing from './pages/Sharing.jsx';
import Assistant from './pages/Assistant.jsx';
import EmergencyInfo from './pages/EmergencyInfo.jsx';
import SharedPerson from './pages/SharedViews.jsx';
import Search from './pages/Search.jsx';
import NotFound from './pages/NotFound.jsx';

export default function App() {
  return (
    <Routes>
      <Route element={<PublicOnlyRoute />}>
        <Route path="/welcome" element={<Entry />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
      </Route>
      <Route path="/sos" element={<Emergency />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/documents/:id" element={<DocumentDetail />} />
          <Route path="/shared/documents/:id" element={<DocumentDetail shared />} />
          <Route path="/shared/people/:ownerId/:section" element={<SharedPerson />} />
          <Route path="/health" element={<Health />} />
          <Route path="/medicines" element={<Medicines />} />
          <Route path="/diet" element={<Diet />} />
        <Route path="/wellness" element={<Wellness />} />
          <Route path="/timeline" element={<Timeline />} />
          <Route path="/reminders" element={<Reminders />} />
          <Route path="/sharing" element={<Sharing />} />
          <Route path="/assistant" element={<Assistant />} />
          <Route path="/emergency" element={<EmergencyInfo />} />
          <Route path="/search" element={<Search />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/family" element={<Family />} />
          <Route path="/settings" element={<Settings />} />
        </Route>
      </Route>
      <Route path="/index.html" element={<Navigate to="/" replace />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
