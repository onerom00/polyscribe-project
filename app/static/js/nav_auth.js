// static/js/nav_auth.js
document.addEventListener("DOMContentLoaded", () => {
  const login = document.getElementById("nav-login-link");
  const signup = document.getElementById("nav-signup-link");

  function go(path) {
    location.href = path;
  }

  if (login) {
    login.addEventListener("click", (e) => {
      e.preventDefault();
      go("/auth/login");
    });
  }

  if (signup) {
    signup.addEventListener("click", (e) => {
      e.preventDefault();
      go("/auth/register");
    });
  }
});
