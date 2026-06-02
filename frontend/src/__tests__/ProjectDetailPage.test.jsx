/**
 * Tests for the Project Detail page — verifies:
 * 1. The "add member" UI is a <select> dropdown (not a number input)
 * 2. Member names come from m.user.full_name / m.user.email (not m.email)
 */
import { render, screen } from "@testing-library/react";

// ── Next.js / React-Redux ─────────────────────────────────────────────────────
jest.mock("next/navigation", () => ({
    useParams: () => ({ id: "42" }),
}));

jest.mock("react-redux", () => ({
    useSelector: () => ({ id: 99, role: "project_leader" }),
}));

// ── RTK Query hooks ───────────────────────────────────────────────────────────
const mockProject = {
    id: 42,
    name: "Test Project",
    description: "A test project",
    leader_id: 99,
};

const mockMembers = [
    {
        id: 1,
        user_id: 10,
        project_id: 42,
        user: { id: 10, email: "dev@example.com", full_name: "Dev User", role: "developer" },
    },
    {
        id: 2,
        user_id: 11,
        project_id: 42,
        user: { id: 11, email: "qa@example.com", full_name: null, role: "qa" },
    },
];

const mockCandidates = [
    { id: 20, email: "candidate@example.com", full_name: "Candidate One", role: "developer", is_active: true },
];

jest.mock("@/store/features/projects/projectsApi", () => ({
    useGetProjectQuery:        () => ({ data: mockProject, isLoading: false }),
    useGetProjectMembersQuery: () => ({ data: mockMembers, isLoading: false }),
    useGetMemberCandidatesQuery: () => ({ data: mockCandidates, isLoading: false }),
    useAddProjectMemberMutation:    () => [jest.fn(), { isLoading: false }],
    useRemoveProjectMemberMutation: () => [jest.fn()],
}));

jest.mock("@/store/features/labels/labelsApi", () => ({
    useGetProjectLabelsQuery: () => ({ data: [] }),
    useCreateLabelMutation:   () => [jest.fn(), { isLoading: false }],
    useDeleteLabelMutation:   () => [jest.fn()],
}));

jest.mock("@/store/features/stats/statsApi", () => ({
    useGetProjectStatsQuery: () => ({ data: null }),
}));

jest.mock("@/components/RoleGate/page", () => ({
    __esModule: true,
    default: ({ children }) => <>{children}</>,
}));

import ProjectDetailPage from "@/app/(protected)/projects/[id]/page";

// ── Tests ─────────────────────────────────────────────────────────────────────
describe("ProjectDetailPage — member management", () => {
    it("renders a <select> for adding members, not a number input", () => {
        render(<ProjectDetailPage />);
        // spinbutton = type="number" — must not be present
        expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
        // The add-member select should exist
        expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("lists candidates in the dropdown", () => {
        render(<ProjectDetailPage />);
        expect(screen.getByText("Candidate One")).toBeInTheDocument();
    });

    it("displays member full_name from m.user.full_name", () => {
        render(<ProjectDetailPage />);
        expect(screen.getByText("Dev User")).toBeInTheDocument();
    });

    it("falls back to m.user.email when full_name is null", () => {
        render(<ProjectDetailPage />);
        expect(screen.getByText("qa@example.com")).toBeInTheDocument();
    });

    it("shows member role from m.user.role, not m.role", () => {
        render(<ProjectDetailPage />);
        expect(screen.getByText("developer")).toBeInTheDocument();
        expect(screen.getByText("qa")).toBeInTheDocument();
    });
});
