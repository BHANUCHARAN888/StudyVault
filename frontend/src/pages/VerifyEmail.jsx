import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import api from "../services/api";

function VerifyEmail() {
    const [searchParams] = useSearchParams();
    const [status, setStatus] = useState("loading");
    const [message, setMessage] = useState("");
    const verificationStarted = useRef(null);

    const token = searchParams.get("token");

    useEffect(() => {
        if (!token) {
            setStatus("error");
            setMessage("Verification token is missing.");
            return;
        }

        if (verificationStarted.current === token) {
            return;
        }

        verificationStarted.current = token;

        async function verifyEmail() {
            try {
                const response = await api.get("/auth/verify-email", {
                    params: { token },
                });

                setStatus("success");
                setMessage(response.data.message);
            } catch (error) {
                setStatus("error");
                setMessage(
                    error.response?.data?.detail ||
                    "Email verification failed. Please request a new verification email."
                );
            }
        }

        verifyEmail();
    }, [token]);

    return (
        <main className="auth-container">
            <section className="auth-card">
                <h1>StudyVault</h1>

                {status === "loading" && (
                    <p>Verifying your email...</p>
                )}

                {status === "success" && (
                    <>
                        <h2>Email Verified!</h2>
                        <p>{message}</p>
                        <Link to="/login">Continue to Login</Link>
                    </>
                )}

                {status === "error" && (
                    <>
                        <h2>Verification Failed</h2>
                        <p role="alert">{message}</p>
                        <Link to="/login">Back to Login</Link>
                    </>
                )}
            </section>
        </main>
    );
}

export default VerifyEmail;
