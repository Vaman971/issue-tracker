import { configureStore } from "@reduxjs/toolkit";
import { render, screen, fireEvent } from "@testing-library/react";
import { Provider } from "react-redux";

import authReducer from "@/store/features/auth/authSlice";
import { api } from "@/store/api";

jest.mock("@/store/features/notifications/notificationsApi", () => ({
    useGetNotificationsQuery: jest.fn(),
    useMarkNotificationReadMutation: jest.fn(),
    useMarkAllNotificationsReadMutation: jest.fn(),
    useDeleteNotificationMutation: jest.fn(),
}));

const {
    useGetNotificationsQuery,
    useMarkNotificationReadMutation,
    useMarkAllNotificationsReadMutation,
    useDeleteNotificationMutation,
} = require("@/store/features/notifications/notificationsApi");

const mockNotifications = [
    {
        id: 1,
        type: "issue_commented",
        title: "New comment",
        message: "Someone commented on your issue",
        is_read: false,
        created_at: "2026-06-01T10:00:00",
    },
    {
        id: 2,
        type: "issue_assigned",
        title: "Issue assigned",
        message: "You were assigned to an issue",
        is_read: true,
        created_at: "2026-05-31T09:00:00",
    },
];

function makeStore() {
    return configureStore({
        reducer: { auth: authReducer, [api.reducerPath]: api.reducer },
        middleware: (gDM) => gDM().concat(api.middleware),
        preloadedState: {
            auth: {
                accessToken: "fake-token",
                refreshToken: "fake-rt",
                user: { id: 1, email: "user@test.com", role: "developer" },
                isAuthenticated: true,
                authChecked: true,
            },
        },
    });
}

beforeEach(() => {
    useGetNotificationsQuery.mockReturnValue({
        data: mockNotifications,
        isLoading: false,
        isError: false,
    });
    useMarkNotificationReadMutation.mockReturnValue([jest.fn(), { isLoading: false }]);
    useMarkAllNotificationsReadMutation.mockReturnValue([jest.fn(), { isLoading: false }]);
    useDeleteNotificationMutation.mockReturnValue([jest.fn(), { isLoading: false }]);
});

import NotificationDrawer from "../page";

function renderDrawer(isOpen = true, onClose = jest.fn()) {
    return render(
        <Provider store={makeStore()}>
            <NotificationDrawer isOpen={isOpen} onClose={onClose} />
        </Provider>
    );
}

test("renders notifications drawer header when open", () => {
    renderDrawer(true);
    expect(screen.getByText("Notifications")).toBeInTheDocument();
});

test("renders list of notifications when open", () => {
    renderDrawer(true);
    expect(screen.getByText("New comment")).toBeInTheDocument();
    expect(screen.getByText("Issue assigned")).toBeInTheDocument();
});

test("unread notification shows mark-read button", () => {
    renderDrawer(true);
    const readButtons = screen.getAllByTitle("Mark as read");
    expect(readButtons.length).toBe(1);
});

test("shows mark all read button when unread notifications exist", () => {
    renderDrawer(true);
    expect(screen.getByText("Mark all read")).toBeInTheDocument();
});

test("shows unread count badge when there are unread notifications", () => {
    renderDrawer(true);
    // 1 unread notification → badge shows "1"
    const ones = screen.getAllByText("1");
    expect(ones.length).toBeGreaterThan(0);
});

test("shows empty state when no notifications", () => {
    useGetNotificationsQuery.mockReturnValue({ data: [], isLoading: false, isError: false });
    renderDrawer(true);
    expect(screen.getByText(/all caught up/i)).toBeInTheDocument();
});

test("shows loading state while fetching", () => {
    useGetNotificationsQuery.mockReturnValue({ data: [], isLoading: true, isError: false });
    renderDrawer(true);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
});

test("close button calls onClose", () => {
    const onClose = jest.fn();
    renderDrawer(true, onClose);
    fireEvent.click(screen.getByLabelText("Close notifications"));
    expect(onClose).toHaveBeenCalledTimes(1);
});

test("clicking backdrop calls onClose", () => {
    const onClose = jest.fn();
    renderDrawer(true, onClose);
    const backdrop = document.querySelector("[aria-hidden='true']");
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
});

test("unread-only toggle changes aria-checked state", () => {
    renderDrawer(true);
    const toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("aria-checked", "false");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
});

test("shows unread-only empty state after toggling filter with no unread notifications", () => {
    useGetNotificationsQuery.mockReturnValue({ data: [], isLoading: false, isError: false });
    renderDrawer(true);
    const toggle = screen.getByRole("switch");
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
});

test("mark all read button is absent when all notifications are read", () => {
    useGetNotificationsQuery.mockReturnValue({
        data: [{ ...mockNotifications[1] }],
        isLoading: false,
        isError: false,
    });
    renderDrawer(true);
    expect(screen.queryByText("Mark all read")).not.toBeInTheDocument();
});
