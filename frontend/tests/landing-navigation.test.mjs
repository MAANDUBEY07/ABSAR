import test from "node:test";
import assert from "node:assert/strict";

/**
 * Pure helper simulating landing page navigation conditional routing
 * for signed-out vs signed-in user states.
 */
function getLandingNavigation(user) {
  const headerActions = user
    ? [{ label: "Dashboard", href: "/dashboard", className: "header-cta" }]
    : [
        { label: "Log in", href: "/login", className: "header-login" },
        { label: "Get started", href: "/signup", className: "header-cta" },
      ];

  const bottomCta = {
    label: user ? "Update your profile" : "Create your profile",
    href: user ? "/profile" : "/signup",
    className: "hero-primary",
  };

  const resumeCta = {
    label: "Analyze Resume",
    href: user ? "/resume" : "/login",
    className: "hero-secondary",
  };

  return { headerActions, bottomCta, resumeCta };
}

test("Signed-out visitor navigation state", () => {
  const nav = getLandingNavigation(null);

  assert.equal(nav.headerActions.length, 2);
  assert.deepEqual(nav.headerActions[0], { label: "Log in", href: "/login", className: "header-login" });
  assert.deepEqual(nav.headerActions[1], { label: "Get started", href: "/signup", className: "header-cta" });

  assert.equal(nav.bottomCta.label, "Create your profile");
  assert.equal(nav.bottomCta.href, "/signup");

  assert.equal(nav.resumeCta.href, "/login");
});

test("Signed-in user navigation state", () => {
  const user = { id: "user-123", email: "student@example.test" };
  const nav = getLandingNavigation(user);

  assert.equal(nav.headerActions.length, 1);
  assert.deepEqual(nav.headerActions[0], { label: "Dashboard", href: "/dashboard", className: "header-cta" });

  assert.equal(nav.bottomCta.label, "Update your profile");
  assert.equal(nav.bottomCta.href, "/profile");

  assert.equal(nav.resumeCta.href, "/resume");
});
