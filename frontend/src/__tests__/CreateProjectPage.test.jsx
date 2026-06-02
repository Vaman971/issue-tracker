/**
 * Tests for the CreateProjectModal — replaces the old /projects/create page
 * which was converted to a modal.
 */
import { render, screen, fireEvent } from "@testing-library/react";

// Portal renders inline in tests
jest.mock("react-dom", () => ({
    ...jest.requireActual("react-dom"),
    createPortal: (node) => node,
}));

// RTK Query needs all three react-redux hooks at module init time
jest.mock("react-redux", () => ({
    useSelector: jest.fn(() => ({})),
    useDispatch: jest.fn(() => jest.fn()),
    useStore: jest.fn(() => ({
        getState: jest.fn(() => ({})),
        dispatch: jest.fn(),
        subscribe: jest.fn(() => jest.fn()),
    })),
}));

const mockCreateProject = jest.fn();
jest.mock("@/store/features/projects/projectsApi", () => ({
    useCreateProjectMutation: () => [mockCreateProject, { isLoading: false }],
}));

const mockLeaders = [
    { id: 1, email: "alice@example.com", full_name: "Alice Smith", role: "project_leader" },
    { id: 2, email: "bob@example.com",   full_name: null,           role: "admin" },
];

jest.mock("@/store/features/users/usersApi", () => ({
    useGetUserLeadersQuery: () => ({ data: mockLeaders, isLoading: false }),
}));

// Render UserSelect as a lightweight stub that still shows the leader list
jest.mock("@/components/UserSelect/page", () => ({
    __esModule: true,
    default: ({ users = [], placeholder }) => (
        <div>
            <input placeholder={placeholder} />
            {users.map((u) => (
                <span key={u.id}>{u.full_name || u.email}</span>
            ))}
        </div>
    ),
}));

import CreateProjectModal from "@/components/CreateProjectModal/page";

const onClose = jest.fn();

function renderModal(isOpen = true) {
    return render(<CreateProjectModal isOpen={isOpen} onClose={onClose} />);
}

describe("CreateProjectModal", () => {
    beforeEach(() => onClose.mockClear());

    it("renders no number (spinbutton) input", () => {
        renderModal();
        expect(screen.queryByRole("spinbutton")).not.toBeInTheDocument();
    });

    it("has a project name text input", () => {
        renderModal();
        expect(screen.getByPlaceholderText(/project name/i)).toBeInTheDocument();
    });

    it("shows a leader search field via UserSelect", () => {
        renderModal();
        expect(screen.getByPlaceholderText(/search for a leader/i)).toBeInTheDocument();
    });

    it("populates leader options from the API", () => {
        renderModal();
        expect(screen.getByText("Alice Smith")).toBeInTheDocument();
        expect(screen.getByText("bob@example.com")).toBeInTheDocument();
    });

    it("has a Create Project submit button", () => {
        renderModal();
        expect(screen.getByRole("button", { name: /create project/i })).toBeInTheDocument();
    });

    it("has a Cancel button that calls onClose", () => {
        renderModal();
        fireEvent.click(screen.getByRole("button", { name: /cancel/i }));
        expect(onClose).toHaveBeenCalled();
    });

    it("still mounts form DOM when isOpen is false (hidden via CSS, not unmounted)", () => {
        // The modal uses CSS opacity/pointer-events to hide, not conditional rendering.
        // This test documents that the submit button is in the DOM even when closed.
        renderModal(false);
        expect(screen.getByRole("button", { name: /create project/i })).toBeInTheDocument();
    });
});
