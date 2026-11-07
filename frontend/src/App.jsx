import { useState, useEffect } from "react";
import {
  Navigate,
  Route,
  Routes,
  useOutletContext,
  useParams,
} from "react-router-dom";
import { useAuth } from "./context/AuthContext";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Subjects from "./pages/Subjects";
import VerifyEmail from "./pages/VerifyEmail";
import ForgotPassword from "./pages/ForgotPassword";
import ResetPassword from "./pages/ResetPassword";
import ProtectedLayout from "./layouts/ProtectedLayout";
import api from "./services/api";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  FileText,
  Link2,
  Menu,
  MoreVertical,
  Pencil,
  Search,
  Trash2,
  Upload,
  UserRound,
} from "lucide-react";

import "./App.css";

function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }

  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function DocumentCard({ document, onDelete, onOpen, onEdit }) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <article className="document-card">
      <div className="document-preview">
        <button
          type="button"
          className="document-open-button"
          onClick={() => onOpen(document)}
          aria-label={`Open PDF: ${document.title}`}
          title="Open PDF"
        >
          <FileText size={54} strokeWidth={1.3} />
          <span className="pdf-label">PDF DOCUMENT</span>
        </button>

        <div className="document-menu-container">
          <button
            className="icon-button document-menu-button"
            type="button"
            aria-label={`Actions for ${document.title}`}
            aria-expanded={menuOpen}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <MoreVertical size={18} />
          </button>

          {menuOpen && (
            <div className="document-dropdown">
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onOpen(document);
                }}
              >
                <FileText size={14} />
                Open PDF
              </button>

              <button
                type="button"
                className="document-delete-action"
                onClick={() => {
                  setMenuOpen(false);
                  onDelete(document);
                }}
              >
                <Trash2 size={14} />
                Delete
              </button>
              <button
                type="button"
                onClick={() => {
                  setMenuOpen(false);
                  onEdit(document);
                }}
              >
                <Pencil size={14} />
                Rename / Edit
              </button>

            </div>
          )}
        </div>
      </div>

      <div className="document-card-details">
        <h2 className="document-name" title={document.title}>
          {document.title}
        </h2>

        <p className="document-size">
          {formatFileSize(document.file_size)}
        </p>
      </div>
    </article>
  );
}

function Dashboard() {

  const { subjectId } = useParams();
  const { user, logout } = useAuth();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const { mobileSidebarOpen, setMobileSidebarOpen } = useOutletContext(); const [documents, setDocuments] = useState([]);
  const [subjects, setSubjects] = useState([]);

  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadSubjectId, setUploadSubjectId] = useState("");

  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editingDocument, setEditingDocument] = useState(null);
  const [editTitle, setEditTitle] = useState("");
  const [editSubjectId, setEditSubjectId] = useState("");

  const [loadingData, setLoadingData] = useState(true);
  const [dataError, setDataError] = useState("");
  const [currentPage, setCurrentPage] = useState(1);
  const documentsPerPage = 8;

  const [searchTerm, setSearchTerm] = useState("");
  const [selectedSubject, setSelectedSubject] = useState("");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortOrder, setSortOrder] = useState("desc");
  const [totalDocuments, setTotalDocuments] = useState(0);

  const totalPages = Math.max(
    1,
    Math.ceil(totalDocuments / documentsPerPage),
  );

  const currentDocuments = documents;

  async function onOpenDocument(document) {
    let pdfWindow = null;
    let objectUrl = null;

    try {
      // Open a blank tab immediately to reduce popup-blocker issues.
      pdfWindow = window.open("about:blank", "_blank");

      const response = await api.get(
        `/documents/${document.id}/file`,
        { responseType: "blob" },
      );

      objectUrl = URL.createObjectURL(
        new Blob([response.data], { type: "application/pdf" }),
      );

      if (pdfWindow) {
        pdfWindow.location.href = objectUrl;

        // Keep the URL available while the PDF is being viewed.
        window.setTimeout(() => {
          URL.revokeObjectURL(objectUrl);
        }, 60 * 60 * 1000);
      } else {
        URL.revokeObjectURL(objectUrl);
        alert("Your browser blocked the PDF tab. Please allow pop-ups and try again.");
      }
    } catch (error) {
      if (pdfWindow && !pdfWindow.closed) {
        pdfWindow.close();
      }

      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }

      const message =
        error.response?.data?.detail ||
        "Unable to open this PDF. Please check your login and try again.";

      alert(typeof message === "string" ? message : "Unable to open this PDF.");
      console.error("PDF opening failed:", error);
    }
  }

  async function onDeleteDocument(document) {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${document.title}"?`,
    );

    if (!confirmed) return;

    try {
      await api.delete(`/documents/${document.id}`);

      setDocuments((previousDocuments) =>
        previousDocuments.filter((item) => item.id !== document.id),
      );
    } catch (error) {
      const message =
        typeof error.response?.data?.detail === "string"
          ? error.response.data.detail
          : "Unable to delete this document. Please try again.";

      alert(message);
      console.error("Document deletion failed:", error);
    }
  }

  function onEditDocument(document) {
    setEditingDocument(document);
    setEditTitle(document.title);
    setEditSubjectId(
      document.subject_id == null ? "" : String(document.subject_id),
    );
    setEditModalOpen(true);
  }

  async function updateDocumentTitle(document, title, subjectId) {
    try {
      const payload = {
        title,
        subject_id: subjectId === "" ? null : Number(subjectId),
      };

      const response = await api.patch(
        `/documents/${document.id}`,
        payload,
      );

      setDocuments((previousDocuments) =>
        previousDocuments.map((item) =>
          item.id === document.id ? response.data : item,
        ),
      );

      setEditModalOpen(false);
      setEditingDocument(null);
    } catch (error) {
      const message =
        typeof error.response?.data?.detail === "string"
          ? error.response.data.detail
          : "Unable to update this document. Please try again.";

      alert(message);
      console.error("Document update failed:", error);
    }
  }

  async function handleUpload(event) {
    event.preventDefault();

    if (!uploadFile) {
      alert("Please select a PDF file.");
      return;
    }

    const title = uploadTitle.trim();

    if (!title) {
      alert("Please enter a document title.");
      return;
    }

    const formData = new FormData();
    formData.append("file", uploadFile);
    formData.append("title", title);

    if (uploadSubjectId) {
      formData.append("subject_id", uploadSubjectId);
    }

    try {
      await api.post("/documents/", formData);

      // Refresh the document list after a successful upload.
      const response = await api.get("/documents/");
      setDocuments(response.data);

      setCurrentPage(1);
      setUploadModalOpen(false);
      setUploadFile(null);
      setUploadTitle("");
      setUploadSubjectId("");

      alert("PDF uploaded successfully!");
    } catch (error) {
      const message =
        typeof error.response?.data?.detail === "string"
          ? error.response.data.detail
          : "Unable to upload the PDF. Please try again.";

      alert(message);
      console.error("Document upload failed:", error);
    }
  }

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      setLoadingData(true);
      setDataError("");

      try {
        const params = {
          limit: 8,
          offset: (currentPage - 1) * 8,
          sort_by: sortBy,
          order: sortOrder,
        };

        if (searchTerm.trim()) {
          params.search = searchTerm.trim();
        }

        const activeSubjectId = subjectId || selectedSubject;

        if (activeSubjectId) {
          params.subject_id = Number(activeSubjectId);
        }

        const [documentsResponse, subjectsResponse] = await Promise.all([
          api.get("/documents/", { params }),
          api.get("/subjects/"),
        ]);

        if (cancelled) return;

        setDocuments(documentsResponse.data);
        setTotalDocuments(
          Number(documentsResponse.headers["x-total-count"] ?? 0)
        );
        setSubjects(subjectsResponse.data);
      } catch (error) {
        if (cancelled) return;

        setDataError(
          typeof error.response?.data?.detail === "string"
            ? error.response.data.detail
            : "Unable to load your documents. Please try again.",
        );
      } finally {
        if (!cancelled) {
          setLoadingData(false);
        }
      }
    }

    loadDashboard();

    return () => {
      cancelled = true;
    };
  }, [currentPage, searchTerm, selectedSubject, sortBy, sortOrder, subjectId]);

  return (
    <main className="dashboard-main">

      <header className="topbar">
        <button
          className="mobile-menu-button"
          aria-label={mobileSidebarOpen ? "Close navigation" : "Open navigation"}
          aria-controls="studyvault-sidebar"
          aria-expanded={mobileSidebarOpen}
          type="button"
          onClick={() => setMobileSidebarOpen((open) => !open)}
        >
          <Menu size={17} />
        </button>

        <h1 className="page-title">My Documents</h1>

        <div className="topbar-actions">
          <button
            className="button button-primary"
            type="button"
            onClick={() => setUploadModalOpen(true)}
          >
            <Upload size={11} />
            Upload PDF
          </button>
        </div>
      </header>

      <section className="dashboard-content">
        <div className="toolbar">
          <label className="search-control">
            <Search size={12} />

            <input
              className="input-control"
              type="search"
              placeholder="Search"
              aria-label="Search documents"
              value={searchTerm}
              onChange={(event) => {
                setSearchTerm(event.target.value);
                setCurrentPage(1);
              }}
            />
          </label>

          <select className="select-control" value={selectedSubject}
            onChange={(event) => {
              setSelectedSubject(event.target.value);
              setCurrentPage(1);
            }}>
            <option value="">All Subjects</option>
            {subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                {subject.name}
              </option>
            ))}
          </select>

          <select
            className="select-control"
            value={sortBy}
            onChange={(event) => {
              setSortBy(event.target.value);
              setCurrentPage(1);
            }}
          >
            <option value="created_at">Date created</option>
            <option value="title">Title</option>
            <option value="file_size">File size</option>
          </select>
        </div>

        <p className="document-count">
          Total Documents: {documents.length}
        </p>

        {editModalOpen && editingDocument && (
          <div
            className="modal-backdrop"
            onClick={(event) => {
              if (event.target === event.currentTarget) {
                setEditModalOpen(false);
                setEditingDocument(null);
              }
            }}
          >
            <section
              className="upload-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="edit-modal-title"
            >
              <h2 id="edit-modal-title">Edit Document</h2>

              <form
                onSubmit={(event) => {
                  event.preventDefault();

                  const trimmedTitle = editTitle.trim();

                  if (!trimmedTitle) {
                    alert("Document title cannot be empty.");
                    return;
                  }

                  updateDocumentTitle(
                    editingDocument,
                    trimmedTitle,
                    editSubjectId,
                  );
                }}
              >
                <label className="form-label" htmlFor="edit-title">
                  Document title
                </label>

                <input
                  id="edit-title"
                  className="input-control"
                  type="text"
                  value={editTitle}
                  onChange={(event) => setEditTitle(event.target.value)}
                  maxLength={255}
                  required
                />

                <label className="form-label" htmlFor="edit-subject">
                  Subject
                </label>

                <select
                  id="edit-subject"
                  className="select-control"
                  value={editSubjectId}
                  onChange={(event) => setEditSubjectId(event.target.value)}
                >
                  <option value="">No subject</option>

                  {subjects.map((subject) => (
                    <option key={subject.id} value={subject.id}>
                      {subject.name}
                    </option>
                  ))}
                </select>

                <div className="modal-actions">
                  <button
                    className="button"
                    type="button"
                    onClick={() => {
                      setEditModalOpen(false);
                      setEditingDocument(null);
                    }}
                  >
                    Cancel
                  </button>

                  <button className="button button-primary" type="submit">
                    Save Changes
                  </button>
                </div>
              </form>
            </section>
          </div>
        )}

        {uploadModalOpen && (
          <div
            className="modal-backdrop"
            onClick={(event) => {
              if (event.target === event.currentTarget) {
                setUploadModalOpen(false);
              }
            }}
          >
            <section
              className="upload-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="upload-modal-title"
            >
              <h2 id="upload-modal-title">Upload PDF</h2>

              <form onSubmit={handleUpload}>
                <label className="form-label" htmlFor="upload-file">
                  Select PDF
                </label>

                <input
                  id="upload-file"
                  type="file"
                  accept="application/pdf,.pdf"
                  onChange={(event) => {
                    setUploadFile(event.target.files?.[0] || null);
                  }}
                  required
                />

                <label className="form-label" htmlFor="upload-title">
                  Document title
                </label>

                <input
                  id="upload-title"
                  className="input-control"
                  type="text"
                  value={uploadTitle}
                  onChange={(event) => setUploadTitle(event.target.value)}
                  placeholder="Enter document title"
                  maxLength={255}
                  required
                />

                <label className="form-label" htmlFor="upload-subject">
                  Subject (optional)
                </label>

                <select
                  id="upload-subject"
                  className="select-control"
                  value={uploadSubjectId}
                  onChange={(event) => setUploadSubjectId(event.target.value)}
                >
                  <option value="">No subject</option>

                  {subjects.map((subject) => (
                    <option key={subject.id} value={subject.id}>
                      {subject.name}
                    </option>
                  ))}
                </select>

                <div className="modal-actions">
                  <button
                    className="button"
                    type="button"
                    onClick={() => {
                      setUploadModalOpen(false);
                      setUploadFile(null);
                      setUploadTitle("");
                      setUploadSubjectId("");
                    }}
                  >
                    Cancel
                  </button>

                  <button className="button button-primary" type="submit">
                    <Upload size={14} />
                    Upload
                  </button>
                </div>
              </form>
            </section>
          </div>
        )}

        {loadingData ? (
          <p className="dashboard-message">Loading your documents...</p>
        ) : dataError ? (
          <p className="dashboard-error" role="alert">{dataError}</p>
        ) : documents.length === 0 ? (
          <p className="dashboard-message">
            No documents yet. Upload your first PDF to get started.
          </p>
        ) : (
          <div className="document-grid">
            {currentDocuments.map((document) => (
              <DocumentCard
                key={document.id}
                document={document}
                onDelete={onDeleteDocument}
                onOpen={onOpenDocument}
                onEdit={onEditDocument}
              />
            ))}
          </div>
        )}

        <nav className="pagination" aria-label="Document pages">
          <button
            type="button"
            aria-label="Previous page"
            disabled={currentPage === 1}
            onClick={() => setCurrentPage((page) => page - 1)}
          >
            <ChevronLeft size={13} />
          </button>

          {Array.from({ length: totalPages }, (_, index) => index + 1).map((page) => (
            <button
              type="button"
              className={page === currentPage ? "active" : ""}
              key={page}
              aria-current={page === currentPage ? "page" : undefined}
              onClick={() => setCurrentPage(page)}
            >
              {page}
            </button>
          ))}

          <button
            type="button"
            aria-label="Next page"
            disabled={currentPage === totalPages}
            onClick={() => setCurrentPage((page) => page + 1)}
          >
            <ChevronRight size={13} />
          </button>
        </nav>
      </section>
    </main>
  );
}

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="auth-loading">Loading StudyVault...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return children;
}

function GuestRoute({ children }) {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="auth-loading">Loading StudyVault...</div>;
  }

  if (user) {
    return <Navigate to="/" replace />;
  }

  return children;
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <GuestRoute>
            <Login />
          </GuestRoute>
        }
      />

      <Route
        path="/register"
        element={
          <GuestRoute>
            <Register />
          </GuestRoute>
        }
      />
      <Route
        path="/forgot-password"
        element={
          <GuestRoute>
            <ForgotPassword />
          </GuestRoute>
        }
      />
      <Route
        path="/reset-password"
        element={
          <GuestRoute>
            <ResetPassword />
          </GuestRoute>
        }
      />
      <Route path="/verify-email" element={<VerifyEmail />} />

      <Route
        element={
          <ProtectedRoute>
            <ProtectedLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<Dashboard />} />
        <Route path="/subjects" element={<Subjects />} />
        <Route path="/subjects/:subjectId" element={<Dashboard />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}