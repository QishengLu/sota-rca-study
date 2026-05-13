import { Routes, Route } from 'react-router-dom';
import { Layout } from './components/layout';
import { OverviewPage } from './pages/OverviewPage';
import { CaseListPage } from './pages/CaseListPage';
import { CaseDetailPage } from './pages/CaseDetailPage';
import { ComparisonPage } from './pages/ComparisonPage';

function App() {
  return (
    <Routes>
      <Route path="/" element={<Layout />}>
        <Route index element={<OverviewPage />} />
        <Route path="cases" element={<CaseListPage />} />
        <Route path="cases/:id" element={<CaseDetailPage />} />
        <Route path="comparison" element={<ComparisonPage />} />
      </Route>
    </Routes>
  );
}

export default App;
