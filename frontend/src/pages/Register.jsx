
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BookOpen,
  Eye,
  EyeOff,
  LockKeyhole,
  Mail,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    if (password.length < 8) {
      setError("Password must contain at least 8 characters.");
      return;
    }

    setSubmitting(true);

    try {
      await register(email.trim(), password);

      navigate("/login", {
        replace: true,
        state: {
          message:
            "Account created successfully. Please check your email to verify your account before signing in.",
        },
      });
    } catch (err) {
      console.log("Registration error:", err);
      console.log("Response status:", err.response?.status);
      console.log("Response data:", err.response?.data);
      console.log("Error message:", err.message);

      const detail = err.response?.data?.detail;

      setError(
        typeof detail === "string"
          ? detail
          : "Registration failed. Please check your details and try again.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="auth-page">
      <section className="auth-layout auth-register-layout">
        <Link to="/login" className="auth-brand">
          <div className="auth-logo">
            <BookOpen size={23} strokeWidth={2.2} />
          </div>
          <span>StudyVault</span>
        </Link>

        <div className="auth-card">
          <div className="auth-heading">
            <h1>Create your account</h1>
            <p>
              Start organizing your study materials in one secure place.
            </p>
          </div>

          {error && (
            <div className="auth-error" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit}>
            <div className="auth-field">
              <label htmlFor="register-email">Email address</label>
              <div className="auth-input-wrapper">
                <Mail size={17} aria-hidden="true" />
                <input
                  id="register-email"
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
              <label htmlFor="register-password">Password</label>
              <div className="auth-input-wrapper">
                <LockKeyhole size={17} aria-hidden="true" />
                <input
                  id="register-password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Create a strong password"
                  minLength={8}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                />
                <button
                  className="auth-password-toggle"
                  type="button"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  onClick={() => setShowPassword((visible) => !visible)}
                >
                  {showPassword ? (
                    <EyeOff size={17} />
                  ) : (
                    <Eye size={17} />
                  )}
                </button>
              </div>
              <small className="auth-field-hint">
                Use at least 8 characters and meet the password requirements.
              </small>
            </div>

            <div className="auth-field">
              <label htmlFor="confirm-password">Confirm password</label>
              <div className="auth-input-wrapper">
                <LockKeyhole size={17} aria-hidden="true" />
                <input
                  id="confirm-password"
                  type={showConfirmPassword ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Enter your password again"
                  value={confirmPassword}
                  onChange={(event) =>
                    setConfirmPassword(event.target.value)
                  }
                  required
                />
                <button
                  className="auth-password-toggle"
                  type="button"
                  aria-label={
                    showConfirmPassword ? "Hide password" : "Show password"
                  }
                  onClick={() =>
                    setShowConfirmPassword((visible) => !visible)
                  }
                >
                  {showConfirmPassword ? (
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
              {submitting ? "Creating account..." : "Create account"}
              {!submitting && <ArrowRight size={17} />}
            </button>
          </form>

          <div className="auth-register-prompt">
            <span>Already have an account?</span>
            <Link to="/login">Sign in</Link>
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
