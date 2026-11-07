import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const registrationMessage = location.state?.message;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await login(email.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      const detail = err.response?.data?.detail;

      setError(
        typeof detail === "string"
          ? detail
          : "Unable to sign in. Please check your credentials.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-layout">
        <div className="auth-brand">
          <div className="auth-logo">
            <BookOpen size={23} strokeWidth={2.2} />
          </div>
          <span>StudyVault</span>
        </div>

        <div className="auth-card">
          <div className="auth-heading">
            <h1>Welcome back</h1>
            <p>
              Sign in to continue to your personal learning space.
            </p>
          </div>

          {registrationMessage && (
            <div className="auth-success" role="status">
              {registrationMessage}
            </div>
          )}

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="auth-field">
              <label htmlFor="email">Email address</label>

              <div className="auth-input-wrapper">
                <Mail size={17} aria-hidden="true" />

                <input
                  id="email"
                  type="email"
                  autoComplete="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  required
                />
              </div>
            </div>

            <div className="auth-field">
              <div className="auth-label-row">
                <label htmlFor="password">Password</label>

                <Link to="/forgot-password" className="auth-text-button">
                  Forgot password?
                </Link>
              </div>

              <div className="auth-input-wrapper">
                <LockKeyhole size={17} aria-hidden="true" />

                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />

                <button
                  className="auth-password-toggle"
                  type="button"
                  aria-label={
                    showPassword ? "Hide password" : "Show password"
                  }
                  onClick={() => setShowPassword((visible) => !visible)}
                >
                  {showPassword ? (
                    <EyeOff size={17} />
                  ) : (
                    <Eye size={17} />
                  )}
                </button>
              </div>
            </div>

            <button
              className="auth-submit-button"
              type="submit"
              disabled={submitting}
            >
              {submitting ? "Signing in..." : "Sign in"}

              {!submitting && <ArrowRight size={17} />}
            </button>
          </form>

          <div className="auth-register-prompt">
            <span>Don't have an account?</span>
            <Link to="/register">Create an account</Link>
          </div>
        </div>

        <div className="auth-footer">
          <span>YOUR LEARNING. YOUR SPACE.</span>
          <span>StudyVault © {new Date().getFullYear()}</span>
        </div>
      </section>
    </main>
  );
}
