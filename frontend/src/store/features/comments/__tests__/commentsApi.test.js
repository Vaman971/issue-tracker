/**
 * Structural tests for commentsApi — verifies the RTK Query endpoints exist
 * and have the correct shape, without making real HTTP calls.
 */
import { commentsApi } from "../commentsApi";

describe("commentsApi", () => {
    it("exports the commentsApi slice", () => {
        expect(commentsApi).toBeDefined();
    });

    it("has getComments endpoint", () => {
        expect(commentsApi.endpoints.getComments).toBeDefined();
    });

    it("has createComment endpoint", () => {
        expect(commentsApi.endpoints.createComment).toBeDefined();
    });

    it("has updateComment endpoint", () => {
        expect(commentsApi.endpoints.updateComment).toBeDefined();
    });

    it("has deleteComment endpoint", () => {
        expect(commentsApi.endpoints.deleteComment).toBeDefined();
    });
});
