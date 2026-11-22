import { createBrowserRouter } from 'react-router-dom';
import { App } from './App';
import { IssuePage } from './pages/IssuePage';
import { ArchivePage } from './pages/ArchivePage';
import { IssueDetailPage } from './pages/IssueDetailPage';
import { ItemPage } from './pages/ItemPage';
import { SubscribePage } from './pages/SubscribePage';
import { KnowledgeBasePage } from './pages/KnowledgeBasePage';

export const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <IssuePage /> },
      { path: 'issues', element: <ArchivePage /> },
      { path: 'issues/:issueId', element: <IssueDetailPage /> },
      { path: 'item/:itemId', element: <ItemPage /> },
      { path: 'settings/subscribe', element: <SubscribePage /> },
      { path: 'kb', element: <KnowledgeBasePage /> },
      { path: 'd/:domain/kb', element: <KnowledgeBasePage /> },
    ],
  },
]);
