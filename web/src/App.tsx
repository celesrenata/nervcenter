import {
  BrowserRouter,
  Routes,
  Route,
} from 'react-router-dom'
import { AuthProvider } from './auth/AuthContext'
import { Layout } from './components/Layout'
import { OverviewView } from './views/OverviewView'
import { SystemsView } from './views/SystemsView'
import { TimelineView } from './views/TimelineView'
import { GoalsView } from './views/GoalsView'
import { TaskDagView } from './views/TaskDagView'
import { AgentsView } from './views/AgentsView'
import { InferenceView } from './views/InferenceView'
import { IncidentsView } from './views/IncidentsView'
import { DecisionsView } from './views/DecisionsView'
import { AskView } from './views/AskView'
import { LoginView } from './views/LoginView'

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginView />} />
          <Route
            path="/"
            element={
              <Layout />
            }
          >
            <Route path="/" element={<OverviewView />} />
            <Route path="/systems" element={<SystemsView />} />
            <Route path="/timeline" element={<TimelineView />} />
            <Route path="/goals" element={<GoalsView />} />
            <Route path="/tasks" element={<TaskDagView />} />
            <Route path="/agents" element={<AgentsView />} />
            <Route path="/inference" element={<InferenceView />} />
            <Route path="/incidents" element={<IncidentsView />} />
            <Route path="/decisions" element={<DecisionsView />} />
            <Route path="/ask" element={<AskView />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App