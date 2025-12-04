-- AlterTable
ALTER TABLE "ScanResult" ADD COLUMN "command" TEXT;
ALTER TABLE "ScanResult" ADD COLUMN "exit_code" INTEGER;
ALTER TABLE "ScanResult" ADD COLUMN "finished_at" DATETIME;
ALTER TABLE "ScanResult" ADD COLUMN "phase" TEXT;
ALTER TABLE "ScanResult" ADD COLUMN "started_at" DATETIME;
