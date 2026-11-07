import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../services/api";

function ResetPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");
    setSuccess("");

    if (!token) {
      setError("Invalid or missing password reset token.");
      return;
    }

    if (newPassword !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);

    try {
      const response = await api.post("/auth/reset-password", {
        token,
        new_password: newPassword,
      });

      setSuccess(response.data.message);
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Unable to reset your password. Please try again.",
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page">
      <div className="auth-layout">
        <section className="auth-card">
          <div className="auth-heading">
            <h1>Reset password</h1>
            <p>Create a new password for your StudyVault account.</p>
          </div>

          {success ? (
            <>
              <div className="auth-success">{success}</div>

              <Link className="auth-submit-button" to="/login">
                Go to login
              </Link>
            </>
          ) : (
            <form onSubmit={handleSubmit}>
              <div className="auth-field">
                <label className="auth-label-row" htmlFor="new-password">
                  New password
                </label>

                <div className="auth-input-wrapper">
                  <input
                    id="new-password"
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    placeholder="Enter new password"
                    autoComplete="new-password"
                    minLength={8}
                    maxLength={128}
                    required
                  />
                </div>
              </div>

              <div className="auth-field">
                <label className="auth-label-row" htmlFor="confirm-password">
                  Confirm password
                </label>

                <div className="auth-input-wrapper">
                  <input
                    id="confirm-password"
                    type="password"
                    value={confirmPassword}
                    onChange={(event) =>
                      setConfirmPassword(event.target.value)
                    }
                    placeholder="Confirm new password"
                    autoComplete="new-password"
                    required
                  />
                </div>
              </div>

              <p className="auth-field-hint">
                Use 8–128 characters with at least one uppercase letter,
                one lowercase letter, and one number.
              </p>

              {error && <div className="auth-error">{error}</div>}

              <button
                className="auth-submit-button"
                type="submit"
                disabled={loading}
              >
                {loading ? "Resetting..." : "Reset password"}
              </button>
            </form>
          )}

          {!success && (
            <div className="auth-register-prompt">
              Remember your password? <Link to="/login">Back to login</Link>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

export default ResetPassword;