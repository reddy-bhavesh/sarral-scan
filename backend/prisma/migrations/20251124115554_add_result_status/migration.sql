-- RedefineTables
PRAGMA defer_foreign_keys=ON;
PRAGMA foreign_keys=OFF;
CREATE TABLE "new_ScanResult" (
    "id" INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
    "scanId" INTEGER NOT NULL,
    "tool" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'Pending',
    "raw_output" TEXT NOT NULL,
    "gemini_summary" TEXT,
    "severity" TEXT,
    "cveId" TEXT,
    "createdAt" DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "ScanResult_scanId_fkey" FOREIGN KEY ("scanId") REFERENCES "Scan" ("id") ON DELETE RESTRICT ON UPDATE CASCADE
);
INSERT INTO "new_ScanResult" ("createdAt", "cveId", "gemini_summary", "id", "raw_output", "scanId", "severity", "tool") SELECT "createdAt", "cveId", "gemini_summary", "id", "raw_output", "scanId", "severity", "tool" FROM "ScanResult";
DROP TABLE "ScanResult";
ALTER TABLE "new_ScanResult" RENAME TO "ScanResult";
PRAGMA foreign_keys=ON;
PRAGMA defer_foreign_keys=OFF;
