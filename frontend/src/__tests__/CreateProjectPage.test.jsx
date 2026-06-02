/**
 * Tests for the Create Project page — verifies the leader field is a
 * searchable <select> dropdown instead of a raw number input.
 */
import { render, screen } from "@testing-library/react";

// ── Next.js navigation ───────────────────────────────────────────────────────
jest.mock("next/navigation", () => ({ redirect: jest.fn() }));

// ── RTK Query hooks ───────────────────────────────────────────────────────────
const mockCreateProject = jest.fn();
jest.mock("@/store/features/projects/projectsApi", () => ({
    useCreateProjectMutation: () => [mockCreateProject, { isLoading: false, error: null }],
}));

const mockLeaders = [
    { id: 1, email: "alice@example.com", full_name: "Alice Smith", role: "project_leader", is_active: true, is_email_verified: true },
    { id: 2, email: "bob@example.com",   full_name: null,           role: "admin",          is_active: true, is_email_verified: true },
];

jest.mock("@/store/features/users/usersApi", () => ({
    useGetUserLeadersQuery: () => ({ data: mockLeaders, isLoading: false }),
}));

import CreateProjectPage from "@/app/(protected)/projects/create/page";

// ── Tests ─────────────────────────────────────────────────────────────────────
describe("CreateProjectPage — leader field", () => {
    it("renders a <select> dropdown, not a number input", () => {
        render(<CreateProjectPage />);
        // spinbutton = type="number" input — must not exist
        expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
        // combobox = <select>
        expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("populates dropdown with leader names", () => {
        render(<CreateProjectPage />);
        expect(screen.getByText("Alice Smith")).toBeInTheDocument();
        // Bob has no full_name so email is shown as fallback
        expect(screen.getByText("bob@example.com")).toBeInTheDocument();
    });

    it("shows a placeholder option as the first entry", () => {
        render(<CreateProjectPage />);
        const options = screen.getAllByRole("option");
        expect(options[0]).toHaveTextContent(/select a leader/i);
    });

    it("renders a submit button", () => {
        render(<CreateProjectPage />);
        expect(screen.getByRole("button", { name: /create project/i })).toBeInTheDocument();
    });
});
