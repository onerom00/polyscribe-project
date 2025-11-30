// static/js/nav_auth.js
document.addEventListener("DOMContentLoaded", () => {
  const login = document.getElementById("nav-login-link");
  const signup = document.getElementById("nav-signup-link");

  function go(url) {
    // Propaga ?user_id si ya está en la URL actual
    const uid = new URLSearchParams(location.search).get("user_id");
    const u = new URL(url, location.origin);
    if (uid) u.searchParams.set("user_id", uid);
    location.href = u.pathname + (u.search ? "?" + u.searchParams.toString() : "");
  }

  if (login) {
    login.addEventListener("click", (e) => {
      e.preventDefault();
      go("/dev-login");
    });
  }
  if (signup) {
    signup.addEventListener("click", (e) => {
      e.preventDefault();
      go("/dev-login?signup=1");
    });
  }
});
