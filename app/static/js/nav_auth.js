// static/js/nav_auth.js
document.addEventListener("DOMContentLoaded", () => {
  const login =
    document.getElementById("nav-login-link") ||
    document.querySelector('a[href="/auth/login"]') ||
    document.querySelector('a[href="/dev-login"]');

  const signup =
    document.getElementById("nav-signup-link") ||
    document.querySelector('a[href="/auth/register"]') ||
    document.querySelector('a[href*="signup=1"]');

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
