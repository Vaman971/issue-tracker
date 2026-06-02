/**
 * Structural tests for notificationsApi — verifies the RTK Query endpoints
 * exist and have the correct shape, without making real HTTP calls.
 */
import { notificationsApi } from "../notificationsApi";

describe("notificationsApi", () => {
    it("exports the notificationsApi slice", () => {
        expect(notificationsApi).toBeDefined();
    });

    it("has getNotifications endpoint", () => {
        expect(notificationsApi.endpoints.getNotifications).toBeDefined();
    });

    it("has getNotificationCount endpoint", () => {
        expect(notificationsApi.endpoints.getNotificationCount).toBeDefined();
    });

    it("has markNotificationRead endpoint", () => {
        expect(notificationsApi.endpoints.markNotificationRead).toBeDefined();
    });

    it("has markAllNotificationsRead endpoint", () => {
        expect(notificationsApi.endpoints.markAllNotificationsRead).toBeDefined();
    });

    it("has deleteNotification endpoint", () => {
        expect(notificationsApi.endpoints.deleteNotification).toBeDefined();
    });
});
