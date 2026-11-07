import { useState } from "react";
import { Link } from "react-router-dom";
import api from "../services/api";

function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const handleSubmit = async (event) => {
    event.preventDefault();

    setError("");
    setSuccess("");
    setLoading(true);

    try {
      const response = await api.post("/auth/forgot-password", {
        email: email.trim(),
      });

      setSuccess(response.data.message);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          "Unable to process your request. Please try again.",
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
            <h1>Forgot password?</h1>
            <p>
              Enter your registered email address. If an account exists,
              we'll send you a password reset link.
            </p>
          </div>

          <form onSubmit={handleSubmit}>
            <div className="auth-field">
              <label className="auth-label-row" htmlFor="email">
                Email address
              </label>

              <div className="auth-input-wrapper">
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                />
              </div>
            </div>

            {error && <div className="auth-error">{error}</div>}

            {success && <div className="auth-success">{success}</div>}

            <button
              className="auth-submit-button"
              type="submit"
              disabled={loading}
            >
              {loading ? "Sending..." : "Send reset link"}
            </button>
          </form>

          <div className="auth-register-prompt">
            Remember your password? <Link to="/login">Back to login</Link>
          </div>
        </section>
      </div>
    </main>
  );
}

export default ForgotPassword;