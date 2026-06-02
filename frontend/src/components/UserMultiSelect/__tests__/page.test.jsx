import { render, screen, fireEvent } from "@testing-library/react";
import UserMultiSelect from "../page";

const mockUsers = [
    { id: 1, full_name: "Alice Johnson", email: "alice@test.com", role: "developer" },
    { id: 2, full_name: "Bob Smith", email: "bob@test.com", role: "developer" },
    { id: 3, full_name: null, email: "charlie@test.com", role: "qa" },
];

function renderMultiSelect(props = {}) {
    const defaults = {
        users: mockUsers,
        value: [],
        onChange: jest.fn(),
        loading: false,
        placeholder: "Search users...",
    };
    return render(<UserMultiSelect {...defaults} {...props} />);
}

test("renders search input by default", () => {
    renderMultiSelect();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
});

test("shows placeholder when no users selected", () => {
    renderMultiSelect();
    expect(screen.getByPlaceholderText("Search users...")).toBeInTheDocument();
});

test("renders selected users as pills", () => {
    renderMultiSelect({ value: [mockUsers[0]] });
    expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
});

test("renders remove button for each selected user", () => {
    renderMultiSelect({ value: [mockUsers[0], mockUsers[1]] });
    expect(screen.getByLabelText("Remove Alice Johnson")).toBeInTheDocument();
    expect(screen.getByLabelText("Remove Bob Smith")).toBeInTheDocument();
});

test("calls onChange without removed user when pill remove clicked", () => {
    const onChange = jest.fn();
    renderMultiSelect({ value: [mockUsers[0], mockUsers[1]], onChange });
    fireEvent.click(screen.getByLabelText("Remove Alice Johnson"));
    expect(onChange).toHaveBeenCalledWith([mockUsers[1]]);
});

test("opens dropdown on input focus", () => {
    renderMultiSelect();
    fireEvent.focus(screen.getByRole("textbox"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();
});

test("excludes already-selected users from dropdown", () => {
    renderMultiSelect({ value: [mockUsers[0]] });
    fireEvent.focus(screen.getByRole("textbox"));
    expect(screen.queryByText("Alice Johnson")).not.toBeInTheDocument();
    expect(screen.getByText("Bob Smith")).toBeInTheDocument();
});

test("filters dropdown based on search query", () => {
    renderMultiSelect();
    const input = screen.getByRole("textbox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "alice" } });
    expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
    expect(screen.queryByText("Bob Smith")).not.toBeInTheDocument();
});

test("calls onChange with added user when option clicked", () => {
    const onChange = jest.fn();
    renderMultiSelect({ onChange });
    fireEvent.focus(screen.getByRole("textbox"));
    fireEvent.click(screen.getByText("Alice Johnson"));
    expect(onChange).toHaveBeenCalledWith([mockUsers[0]]);
});

test("shows all-selected message when all users are selected", () => {
    renderMultiSelect({ value: mockUsers });
    fireEvent.focus(screen.getByRole("textbox"));
    expect(screen.getByText(/all available users selected/i)).toBeInTheDocument();
});

test("shows no-users-found message when query has no matches", () => {
    renderMultiSelect();
    const input = screen.getByRole("textbox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "xyznotauser" } });
    expect(screen.getByText("No users found")).toBeInTheDocument();
});

test("shows email as display name when full_name is null", () => {
    renderMultiSelect();
    fireEvent.focus(screen.getByRole("textbox"));
    expect(screen.getByText("charlie@test.com")).toBeInTheDocument();
});

test("hides placeholder when users are selected", () => {
    renderMultiSelect({ value: [mockUsers[0]] });
    expect(screen.queryByPlaceholderText("Search users...")).not.toBeInTheDocument();
});
