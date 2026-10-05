const loginForm = document.getElementById("loginForm");
const message = document.getElementById("message");

loginForm.addEventListener("submit", async function(event) {
    event.preventDefault();

    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;

    message.innerText = "Logging in...";

    try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });

        const data = await response.json();

        if (response.ok) {
            message.innerText = data.message;
            message.style.color = "green";
        } else {
            message.innerText = data.detail;
            message.style.color = "red";
        }
    } catch (error) {
        message.innerText = "Unable to connect to backend.";
        message.style.color = "red";
        console.error(error);
    }
});
