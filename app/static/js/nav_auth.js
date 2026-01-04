document.addEventListener("DOMContentLoaded", () => {
  const login = document.getElementById("nav-login-link");
  const signup = document.getElementById("nav-signup-link");

  function go(path) {
    const u = new URL(path, location.origin);
    location.href = u.pathname + (u.search ? "?" + u.searchParams.toString() : "");
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
