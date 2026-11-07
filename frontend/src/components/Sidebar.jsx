import { useLocation, useNavigate } from "react-router-dom";
import { BookOpen, FileText, FolderOpen, LogOut } from "lucide-react";

function Sidebar({ isOpen, onNavigate, user, onLogout }) {
  const navigate = useNavigate();
  const location = useLocation();

  const isDocumentsPage = location.pathname === "/";
  const isSubjectsPage = location.pathname.startsWith("/subjects");

  return (
    <aside
      id="studyvault-sidebar"
      className={`sidebar${isOpen ? " sidebar-open" : ""}`}
      aria-label="Sidebar navigation"
    >
      <div className="brand">
        <BookOpen className="brand-mark" />
        <span>StudyVault</span>
      </div>

      <nav className="sidebar-nav" aria-label="Main navigation">
        <button
          className={`nav-item${isDocumentsPage ? " active" : ""}`}
          type="button"
          onClick={() => {
            navigate("/");
            onNavigate();
          }}
        >
          <FileText size={12} />
          Documents
        </button>

        <button
          className={`nav-item${isSubjectsPage ? " active" : ""}`}
          type="button"
          onClick={() => {
            navigate("/subjects");
            onNavigate();
          }}
        >
          <FolderOpen size={12} />
          Subjects
        </button>
      </nav>
      <div className="sidebar-footer">
        <div className="sidebar-user">
          <div className="sidebar-user-avatar">
            {user?.email?.charAt(0).toUpperCase() || "U"}
          </div>

          <div className="sidebar-user-info">
            <span className="sidebar-user-label">Signed in as</span>
            <span className="sidebar-user-email" title={user?.email}>
              {user?.email || "User"}
            </span>
          </div>
        </div>

        <button
          type="button"
          className="sidebar-logout"
          onClick={onLogout}
        >
          <LogOut size={16} />
          <span>Logout</span>
        </button>
      </div>
    </aside>
  );
}

export default Sidebar;
