/** Displayed brand / product name.
 *  Change this one line to rename the app everywhere it's rendered. */
export const APP_NAME = 'Archivist';

/** Map backend role identifiers to display labels. */
export const ROLE_LABEL: Record<string, string> = {
  admin:   'Admin',
  analyst: 'Editor',
  viewer:  'Viewer',
};

/** Roles allowed to upload documents. Mirrors the backend's
 *  `require_role("admin", "analyst")` on POST /api/jobs — viewers cannot upload. */
export const UPLOAD_ROLES = ['admin', 'analyst'];

/** Whether a user with the given role may upload documents. */
export function canUpload(role: string | undefined): boolean {
  return role !== undefined && UPLOAD_ROLES.includes(role);
}
