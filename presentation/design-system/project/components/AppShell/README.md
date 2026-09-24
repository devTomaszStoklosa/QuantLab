# AppShell

The application frame: a sidebar with the logo, workspace (data universe) switcher, grouped research navigation and a standing disclaimer, plus a top bar with breadcrumbs and search.

- Props: `active` (nav key), `crumbs`, `counts`, `workspace`, `workspaceMeta`, `nav` (items may carry an `href`), `topActions`, `overlay` (for a `Dialog`), `sideFoot`, `search` (`false` hides the search box of an app without search) and `children` (page content).
- Nav keys: `registry`, `runs`, `validation`, `log`, `data`, `signals`, `costs` and `reports`.
