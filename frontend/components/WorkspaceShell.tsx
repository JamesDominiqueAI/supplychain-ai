import { UserButton, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { useRouter } from "next/router";
import { PropsWithChildren } from "react";

interface WorkspaceShellProps extends PropsWithChildren {
  title: string;
  description: string;
}

const NAV_ITEMS = [
  { href: "/dashboard", label: "Overview" },
  { href: "/products", label: "Products" },
  { href: "/orders", label: "Orders" },
  { href: "/movements", label: "Movements" },
  { href: "/reports", label: "Reports" },
  { href: "/audit", label: "Audit" },
  { href: "/suppliers", label: "Suppliers" },
  { href: "/settings", label: "Settings" },
];

export function WorkspaceShell({ title, description, children }: WorkspaceShellProps) {
  const router = useRouter();
  const { user } = useUser();

  return (
    <main className="page dashboard-page">
      <div className="shell dashboard-shell">
        <section className="workspace-header">
          <div>
            <p className="eyebrow">Lakay Business</p>
            <h1>{title}</h1>
            <p className="lede">
              {description}
              {" "}
              Signed in as {user?.fullName || user?.primaryEmailAddress?.emailAddress || "Operator"}.
            </p>
          </div>
          <div className="command-actions">
            <UserButton />
          </div>
        </section>

        <nav className="workspace-nav">
          {NAV_ITEMS.map((item) => {
            const active = router.pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`workspace-tab ${active ? "active" : ""}`}
                prefetch={false}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        {children}
      </div>
    </main>
  );
}
