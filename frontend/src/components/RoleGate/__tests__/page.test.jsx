import { configureStore } from "@reduxjs/toolkit";
import { render, screen } from "@testing-library/react"
import { Provider } from "react-redux";

import RoleGate from "../page";
import authReducer from "@/store/features/auth/authSlice";


function renderWithRole(role) {
    const store = configureStore({
        reducer: {
            auth: authReducer,
        },

        preloadedState: {
            auth: {
                accessToken: "fake-access-token",
                refreshToken: "fake-refresh-token",
                user: {
                    id: 1,
                    email: "test@example.com",
                    role
                },
                isAuthenticated: true,
                authChecked: true
            },
        },
    });

    return render(
        <Provider store={store}>
            <RoleGate allowedRoles={["admin"]}>
                <p>Admin content</p>
            </RoleGate>
        </Provider>
    );
}

test('shows content for allowed role', () => {
  renderWithRole("admin");
    // get by text throws error if it can not find the value
  expect(screen.getByText("Admin content")).toBeInTheDocument();
});

test('hides content for disallowed role', () => {
  renderWithRole("viewer");
    // query by text throws null if it can not find the value
  expect(screen.queryByText("Admin content")).not.toBeInTheDocument();
});
