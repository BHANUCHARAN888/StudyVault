import { useEffect, useState } from "react";
import { FolderOpen, Plus, Menu, MoreVertical, Pencil, Trash2 } from "lucide-react";
import { useNavigate, useOutletContext } from "react-router-dom";
import api from "../services/api";

function Subjects() {
    const [openMenuId, setOpenMenuId] = useState(null);
    const { setMobileSidebarOpen } = useOutletContext();
    const navigate = useNavigate();
    const [subjects, setSubjects] = useState([]);
    const [documents, setDocuments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");
    const [showCreateModal, setShowCreateModal] = useState(false);
    const [subjectName, setSubjectName] = useState("");
    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState("");

    useEffect(() => {
        async function loadSubjects() {
            try {
                setLoading(true);
                setError("");

                const [subjectsResponse, documentsResponse] = await Promise.all([
                    api.get("/subjects/"),
                    api.get("/documents/", {
                        params: {
                            limit: 100,
                            offset: 0,
                        },
                    }),
                ]);

                setSubjects(subjectsResponse.data);
                setDocuments(documentsResponse.data);
            } catch (err) {
                setError(
                    err.response?.data?.detail || "Unable to load subjects.",
                );
            } finally {
                setLoading(false);
            }
        }

        loadSubjects();
    }, []);

    function getDocumentCount(subjectId) {
        return documents.filter(
            (document) => document.subject_id === subjectId,
        ).length;
    }
    async function handleCreateSubject(event) {
        event.preventDefault();

        const trimmedName = subjectName.trim();

        if (!trimmedName) {
            setCreateError("Subject name is required.");
            return;
        }

        try {
            setCreating(true);
            setCreateError("");

            const response = await api.post("/subjects/", {
                name: trimmedName,
            });

            setSubjects((currentSubjects) => [
                ...currentSubjects,
                response.data,
            ]);

            setSubjectName("");
            setShowCreateModal(false);
        } catch (err) {
            setCreateError(
                err.response?.data?.detail || "Unable to create subject.",
            );
        } finally {
            setCreating(false);
        }
    }

    if (loading) {
        return <p className="dashboard-message">Loading subjects...</p>;
    }

    if (error) {
        return <p className="dashboard-message">{error}</p>;
    }

    async function handleEditSubject(subject) {
        const newName = window.prompt("Enter the new subject name:", subject.name);

        if (newName === null) return;

        const trimmedName = newName.trim();

        if (!trimmedName) {
            alert("Subject name cannot be empty.");
            return;
        }

        try {
            const response = await api.patch(`/subjects/${subject.id}`, {
                name: trimmedName,
            });

            setSubjects((current) =>
                current.map((item) =>
                    item.id === subject.id ? response.data : item
                )
            );
        } catch (error) {
            alert(error.response?.data?.detail || "Unable to rename subject.");
        }
    }

    async function handleDeleteSubject(subject) {
        const confirmed = window.confirm(
            `Are you sure you want to delete "${subject.name}"?`
        );

        if (!confirmed) return;

        try {
            await api.delete(`/subjects/${subject.id}`);

            setSubjects((current) =>
                current.filter((item) => item.id !== subject.id)
            );
        } catch (error) {
            alert(error.response?.data?.detail || "Unable to delete subject.");
        }
    }

    return (
        <main className="dashboard-main">
            <header className="topbar">
                <button
                    className="mobile-menu-button"
                    aria-label="Open navigation"
                    aria-controls="studyvault-sidebar"
                    type="button"
                    onClick={() => setMobileSidebarOpen(true)}
                >
                    <Menu size={17} />
                </button>

                <h1 className="page-title">My Subjects</h1>

                <div className="topbar-actions">
                    <button
                        className="button button-primary"
                        type="button"
                        onClick={() => {
                            setCreateError("");
                            setSubjectName("");
                            setShowCreateModal(true);
                        }}
                    >
                        <Plus size={18} />
                        Create Subject
                    </button>
                </div>
            </header>

            {subjects.length === 0 ? (
                <div className="dashboard-message">
                    <FolderOpen size={32} />
                    <p>No subjects yet. Create your first subject to get started.</p>
                </div>
            ) : (
                <div className="subject-grid">
                    {subjects.map((subject) => (
                        <article className="subject-card" key={subject.id}>
                            <button
                                type="button"
                                className="subject-card-open"
                                onClick={() => navigate(`/subjects/${subject.id}`)}
                            >
                                <div className="subject-card-icon">
                                    <FolderOpen size={24} />
                                </div>

                                <h3>{subject.name}</h3>

                                <p>{getDocumentCount(subject.id)} documents</p>
                            </button>

                            <div className="document-menu-container">
                                <button
                                    className="icon-button document-menu-button"
                                    type="button"
                                    aria-label={`Actions for ${subject.name}`}
                                    aria-expanded={openMenuId === subject.id}
                                    onClick={() =>
                                        setOpenMenuId((current) =>
                                            current === subject.id ? null : subject.id
                                        )
                                    }
                                >
                                    <MoreVertical size={18} />
                                </button>

                                {openMenuId === subject.id && (
                                    <div className="document-dropdown">
                                        <button
                                            type="button"
                                            onClick={() => {
                                                setOpenMenuId(null);
                                                handleEditSubject(subject);
                                            }}
                                        >
                                            <Pencil size={14} />
                                            Edit Subject
                                        </button>

                                        <button
                                            type="button"
                                            className="document-delete-action"
                                            onClick={() => {
                                                setOpenMenuId(null);
                                                handleDeleteSubject(subject);
                                            }}
                                        >
                                            <Trash2 size={14} />
                                            Delete Subject
                                        </button>
                                    </div>
                                )}
                            </div>
                        </article>
                    ))}
                </div>
            )}
            {showCreateModal && (
                <div className="modal-backdrop">
                    <div className="upload-modal">
                        <div className="modal-header">
                            <h2>Create Subject</h2>

                            <button
                                type="button"
                                onClick={() => setShowCreateModal(false)}
                                aria-label="Close modal"
                            >
                                ×
                            </button>
                        </div>

                        <form onSubmit={handleCreateSubject}>
                            <label htmlFor="subject-name">Subject name</label>

                            <input
                                id="subject-name"
                                type="text"
                                placeholder="e.g. Machine Learning"
                                value={subjectName}
                                onChange={(event) => setSubjectName(event.target.value)}
                                maxLength={100}
                                required
                            />

                            {createError && (
                                <p className="form-error">{createError}</p>
                            )}

                            <div className="modal-actions">
                                <button
                                    type="button"
                                    onClick={() => setShowCreateModal(false)}
                                    disabled={creating}
                                >
                                    Cancel
                                </button>

                                <button
                                    type="submit"
                                    disabled={creating}
                                >
                                    {creating ? "Creating..." : "Create Subject"}
                                </button>
                            </div>
                        </form>
                    </div>
                </div>
            )}

        </main>
    );
}

export default Subjects;
