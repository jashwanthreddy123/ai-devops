import os

import psycopg2

from fastapi import FastAPI, HTTPException

from pydantic import BaseModel

from prometheus_client import Counter, generate_latest

from fastapi.responses import Response


app = FastAPI(
    title="AI DevOps Login API"
)


# ============================================================
# Prometheus Metrics
# ============================================================

login_requests = Counter(
    "login_requests_total",
    "Total number of login requests"
)


login_success = Counter(
    "login_success_total",
    "Total successful logins"
)


login_failures = Counter(
    "login_failures_total",
    "Total failed logins"
)


# ============================================================
# Environment Variables
# ============================================================

DB_HOST = os.getenv(
    "DB_HOST",
    "postgres"
)

DB_NAME = os.getenv(
    "POSTGRES_DB",
    "login_db"
)

DB_USER = os.getenv(
    "POSTGRES_USER",
    "login_user"
)

DB_PASSWORD = os.getenv(
    "POSTGRES_PASSWORD",
    "login_password"
)


# ============================================================
# Database Connection
# ============================================================

def get_db_connection():

    return psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


# ============================================================
# Login Model
# ============================================================

class LoginRequest(BaseModel):

    username: str

    password: str


# ============================================================
# Health Check
# ============================================================

@app.get("/health")
def health():

    try:

        connection = get_db_connection()

        connection.close()

        return {
            "status": "ok",
            "database": "connected"
        }

    except Exception as error:

        return {
            "status": "error",
            "database": str(error)
        }


# ============================================================
# Login
# ============================================================

@app.post("/login")
def login(request: LoginRequest):

    login_requests.inc()

    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(
            """
            SELECT username
            FROM users
            WHERE username = %s
            AND password = %s
            """,
            (
                request.username,
                request.password
            )
        )


        user = cursor.fetchone()


        cursor.close()

        connection.close()


        if user:

            login_success.inc()

            return {
                "message": "Login successful",
                "username": user[0]
            }


        login_failures.inc()

        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )


    except HTTPException:

        raise


    except Exception as error:

        login_failures.inc()

        raise HTTPException(
            status_code=500,
            detail="Database connection error"
        )


# ============================================================
# Prometheus Metrics
# ============================================================

@app.get("/metrics")
def metrics():

    return Response(
        generate_latest(),
        media_type="text/plain"
    )
