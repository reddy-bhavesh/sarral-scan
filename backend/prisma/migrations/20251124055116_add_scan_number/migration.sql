-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_Scan" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "target" TEXT NOT NULL,
    "scan_number" INTEGER NOT NULL DEFAULT 1,
    "phases" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "date" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "userId" INTEGER NOT NULL,
    "pdfPath" TEXT,
    CONSTRAINT "Scan_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_Scan" ("date", "id", "pdfPath", "phases", "status", "target", "userId") SELECT "date", "id", "pdfPath", "phases", "status", "target", "userId" FROM "Scan";
DROP TABLE "Scan";
ALTER TABLE "new_Scan" RENAME TO "Scan";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
