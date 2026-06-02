/**
 * Tests for the Project Detail page — verifies member management UI.
 * The add-member field uses UserMultiSelect (searchable, pill-based) instead
 * of a plain <select>; member data comes from m.user.* not m.*.
 */
import { render, screen, fireEvent } from "@testing-library/react";

// ── Next.js navigation ────────────────────────────────────────────────────────
jest.mock("next/navigation", () => ({
    useParams: () => ({ id: "42" }),
    useRouter: () => ({ push: jest.fn() }),
}));

// RTK Query needs all three react-redux hooks when the api module is imported
jest.mock("react-redux", () => ({
    useSelector: jest.fn(() => ({ id: 99, role: "project_leader" })),
    useDispatch: jest.fn(() => jest.fn()),
    useStore: jest.fn(() => ({
        getState: jest.fn(() => ({})),
        dispatch: jest.fn(),
        subscribe: jest.fn(() => jest.fn()),
    })),
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
    { id: 20, email: "candidate@example.com", full_name: "Candidate One", role: "developer" },
];

jest.mock("@/store/features/projects/projectsApi", () => ({
    useGetProjectQuery:             () => ({ data: mockProject, isLoading: false }),
    useUpdateProjectMutation:       () => [jest.fn(), { isLoading: false }],
    useGetProjectMembersQuery:      () => ({ data: mockMembers, isLoading: false }),
    useAddProjectMemberMutation:    () => [jest.fn(), { isLoading: false }],
    useRemoveProjectMemberMutation: () => [jest.fn(), { isLoading: false }],
    useGetMemberCandidatesQuery:    () => ({ data: mockCandidates, isLoading: false }),
    useGetProjectIssuesQuery:       () => ({ data: [], isLoading: false }),
}));

jest.mock("@/store/features/labels/labelsApi", () => ({
    useGetProjectLabelsQuery: () => ({ data: [] }),
    useCreateLabelMutation:   () => [jest.fn(), { isLoading: false }],
    useDeleteLabelMutation:   () => [jest.fn()],
}));

jest.mock("@/store/features/stats/statsApi", () => ({
    useGetProjectStatsQuery: () => ({ data: null }),
}));

jest.mock("@/store/features/users/usersApi", () => ({
    useGetUserLeadersQuery: () => ({ data: [], isLoading: false }),
}));

// ── Sub-component stubs ───────────────────────────────────────────────────────
jest.mock("@/components/RoleGate/page", () => ({
    __esModule: true,
    default: ({ children }) => <>{children}</>,
}));

jest.mock("@/components/CreateIssueModal/page", () => ({
    __esModule: true,
    default: () => null,
}));

// UserSelect stub — renders a labelled textbox
jest.mock("@/components/UserSelect/page", () => ({
    __esModule: true,
    default: ({ placeholder }) => (
        <input placeholder={placeholder || "Search leader"} aria-label="Leader search" />
    ),
}));

// UserMultiSelect stub — renders a textbox + visible candidate list
jest.mock("@/components/UserMultiSelect/page", () => ({
    __esModule: true,
    default: ({ users = [], placeholder }) => (
        <div>
            <input placeholder={placeholder || "Search users"} aria-label="Member search" />
            {users.map((u) => (
                <span key={u.id} data-testid="candidate">
                    {u.full_name || u.email}
                </span>
            ))}
        </div>
    ),
}));

import ProjectDetailPage from "@/app/(protected)/projects/[id]/page";

// ── Tests ─────────────────────────────────────────────────────────────────────
describe("ProjectDetailPage — member management", () => {
    it("has no spinbutton (type=number) input", () => {
        render(<ProjectDetailPage />);
        expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
    });

    it("renders the add-member searchable field (UserMultiSelect)", () => {
        render(<ProjectDetailPage />);
        // The stub renders an input with aria-label "Member search"
        expect(screen.getByLabelText("Member search")).toBeInTheDocument();
    });

    it("passes candidates to UserMultiSelect so they are visible", () => {
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

    it("shows member role from m.user.role", () => {
        render(<ProjectDetailPage />);
        expect(screen.getByText("developer")).toBeInTheDocument();
        expect(screen.getByText("qa")).toBeInTheDocument();
    });
});
