from fastapi import APIRouter, Depends, HTTPException
from typing import List
from prisma import Prisma
from app.api.deps import get_db, get_current_user
from app.models.user import UserResponse
from app.models.scan import ScanCreate, ScanResponse, DashboardStats, StatItem, ChartDataPoint, VulnDistribution
from app.services.scan_manager import ScanManager
from datetime import timedelta, datetime
import json
import asyncio

router = APIRouter()

@router.get("/dashboard-stats", response_model=DashboardStats)
async def get_dashboard_stats(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    # 1. Date Calculations
    from datetime import timezone
    now = datetime.now(timezone.utc)
    one_week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # 2. Fetch All Scans (Metadata only needed for most stats)
    # We grab ID, date, status to calculate trends and chart data efficiently.
    # For Vulns, we need results.
    # Optimization: Two queries? 
    # Query 1: Metadata for all scans (fast)
    all_scans = await db.scan.find_many(
        where={"userId": current_user.id},
        order={"date": "desc"},
    )

    # Filter by date ranges
    current_week_scans = [s for s in all_scans if s.date >= one_week_ago]
    last_week_scans = [s for s in all_scans if s.date >= two_weeks_ago and s.date < one_week_ago]

    # Helper for Trends
    def calculate_trend(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100)

    # 3. Overview Stats
    total_scans_count = len(all_scans)
    total_trend = calculate_trend(len(current_week_scans), len(last_week_scans))

    running_count = sum(1 for s in all_scans if s.status == "Running")
    # Running trend usually 0 or N/A, let's keep logic simple
    running_trend = 0 

    completed_cur = sum(1 for s in current_week_scans if s.status == "Completed")
    completed_prev = sum(1 for s in last_week_scans if s.status == "Completed")
    completed_count = sum(1 for s in all_scans if s.status == "Completed")
    completed_trend = calculate_trend(completed_cur, completed_prev)

    failed_cur = sum(1 for s in current_week_scans if s.status == "Failed")
    failed_prev = sum(1 for s in last_week_scans if s.status == "Failed")
    failed_count = sum(1 for s in all_scans if s.status == "Failed")
    failed_trend = calculate_trend(failed_cur, failed_prev)

    # 4. Chart Data (Last 7 Days)
    chart_data = []
    # Create map for O(1) lookup
    # key: YYYY-MM-DD
    
    for i in range(6, -1, -1):
        target_date = (now - timedelta(days=i)).date()
        date_label = target_date.strftime("%b %d") # e.g. "Oct 24"
        
        day_scans = [s for s in all_scans if s.date.date() == target_date]
        
        chart_data.append(ChartDataPoint(
            date=date_label,
            total=len(day_scans),
            completed=sum(1 for s in day_scans if s.status == "Completed"),
            failed=sum(1 for s in day_scans if s.status == "Failed")
        ))

    # 5. Vulnerability Distribution
    # We MUST fetch results for this. But only for scans that have findings.
    # To optimize: Fetch only scanResults where gemini_summary is not null
    # But Prisma 'find_many' on scan_result with join to scan filtered by user...
    # Let's do a direct query on ScanResult joined with Scan.
    
    # We find scan IDs belonging to user first
    user_scan_ids = [s.id for s in all_scans]
    
    vuln_dist = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Info": 0}
    
    if user_scan_ids:
        # Fetch results with summary only
        results_with_summary = await db.scanresult.find_many(
            where={
                "scanId": {"in": user_scan_ids},
                "gemini_summary": {"not": None}
            }
        )
        
        for r in results_with_summary:
            if r.gemini_summary:
                try:
                    summary = json.loads(r.gemini_summary)
                    if "vulnerabilities" in summary:
                        for v in summary["vulnerabilities"]:
                            severity = v.get("Severity", "Info")
                            if severity in vuln_dist:
                                vuln_dist[severity] += 1
                except:
                    pass

    # 6. Recent Scans (Rich)
    # Optimization: Use metadata directly as it now contains summary stats
    recent_scans_response = all_scans[:5]

    return DashboardStats(
        totalScans=StatItem(value=total_scans_count, trend=total_trend),
        runningScans=StatItem(value=running_count, trend=running_trend),
        completedScans=StatItem(value=completed_count, trend=completed_trend),
        failedScans=StatItem(value=failed_count, trend=failed_trend),
        chartData=chart_data,
        vulnDist=VulnDistribution(**vuln_dist),
        recentScans=recent_scans_response
    )

@router.post("/", response_model=ScanResponse)
async def create_scan(
    scan: ScanCreate,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    try:
        print(f"Creating scan for {scan.target} with phases {scan.phases}")
        scan_manager = ScanManager(db)
        return await scan_manager.create_scan(scan, current_user.id)
    except Exception as e:
        print(f"Error creating scan: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[ScanResponse])
async def get_scans(
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    # Reduced payload: Exclude results for main list usage
    return await db.scan.find_many(
        where={"userId": current_user.id},
        order={"date": "desc"},
    )

@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    scan = await db.scan.find_first(
        where={
            "id": scan_id,
            "userId": current_user.id
        },
        include={
            "results": True
        }
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan

@router.post("/{scan_id}/stop")
async def stop_scan(
    scan_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    scan_manager = ScanManager(db)
    success = await scan_manager.stop_scan(scan_id)
    if not success:
        # It might be that it's not running, but we should check if it exists first?
        # Or just return success if it's already stopped?
        # For now, let's assume if it returns False, it wasn't in active_scans.
        # But we might want to update status to Stopped manually if it was stuck?
        # Let's just return a message.
        return {"message": "Scan was not running"}
    return {"message": "Scan stopped successfully"}

@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: Prisma = Depends(get_db)
):
    scan_manager = ScanManager(db)
    success = await scan_manager.delete_scan(scan_id)
    if not success:
        raise HTTPException(status_code=404, detail="Scan not found")
    return {"message": "Scan deleted successfully"}
