import { render, screen, fireEvent } from "@testing-library/react";
import UserSelect from "../page";

const mockUsers = [
    { id: 1, full_name: "Alice Johnson", email: "alice@test.com", role: "project_leader" },
    { id: 2, full_name: "Bob Smith", email: "bob@test.com", role: "developer" },
    { id: 3, full_name: null, email: "charlie@test.com", role: "developer" },
];

function renderSelect(props = {}) {
    const defaults = {
        users: mockUsers,
        value: null,
        onChange: jest.fn(),
        loading: false,
        placeholder: "Search for a user...",
    };
    return render(<UserSelect {...defaults} {...props} />);
}

test("renders search input when no value selected", () => {
    renderSelect();
    expect(screen.getByRole("textbox")).toBeInTheDocument();
});

test("shows selected user when value is provided", () => {
    renderSelect({ value: mockUsers[0] });
    expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
});

test("shows clear button when a user is selected", () => {
    renderSelect({ value: mockUsers[0] });
    expect(screen.getByLabelText("Clear selection")).toBeInTheDocument();
});

test("calls onChange with null when clear button clicked", () => {
    const onChange = jest.fn();
    renderSelect({ value: mockUsers[0], onChange });
    fireEvent.click(screen.getByLabelText("Clear selection"));
    expect(onChange).toHaveBeenCalledWith(null);
});

test("opens dropdown on input focus", () => {
    renderSelect();
    fireEvent.focus(screen.getByRole("textbox"));
    expect(screen.getByRole("listbox")).toBeInTheDocument();
});

test("filters users based on query", () => {
    renderSelect();
    const input = screen.getByRole("textbox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "alice" } });
    expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
    expect(screen.queryByText("Bob Smith")).not.toBeInTheDocument();
});

test("shows all users when query is empty and dropdown is open", () => {
    renderSelect();
    fireEvent.focus(screen.getByRole("textbox"));
    expect(screen.getByText("Alice Johnson")).toBeInTheDocument();
    expect(screen.getByText("Bob Smith")).toBeInTheDocument();
});

test("calls onChange with user object when an option is clicked", () => {
    const onChange = jest.fn();
    renderSelect({ onChange });
    fireEvent.focus(screen.getByRole("textbox"));
    fireEvent.click(screen.getByText("Alice Johnson"));
    expect(onChange).toHaveBeenCalledWith(mockUsers[0]);
});

test("shows user email as name when full_name is null", () => {
    renderSelect();
    fireEvent.focus(screen.getByRole("textbox"));
    expect(screen.getByText("charlie@test.com")).toBeInTheDocument();
});

test("shows no-options message when query has no matches", () => {
    renderSelect();
    const input = screen.getByRole("textbox");
    fireEvent.focus(input);
    fireEvent.change(input, { target: { value: "xyznotauser" } });
    expect(screen.getByText("No users found")).toBeInTheDocument();
});

test("shows loading placeholder when loading is true", () => {
    renderSelect({ loading: true });
    expect(screen.getByPlaceholderText("Loading users...")).toBeInTheDocument();
});
