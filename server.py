import os
import json
import time
from typing import Optional
from fastmcp import FastMCP
import httpx
import asyncio
import logging

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(format="[%(levelname)s]: %(message)s", level=logging.INFO)

# Create an MCP server
mcp = FastMCP("FlightSearch")

# Placeholder for the base URL. This will be updated later.
BASE_URL = os.environ.get("FLIGHT_API_BASE_URL", "https://www.onlinetour.co.kr")

@mcp.tool()
async def search_flights(
    trip_type: str = "RT",
    departure_city: str = "ICN",
    arrival_city: str = "FUK",
    departure_date: str = "2026-03-03",
    return_date: Optional[str] = "2026-03-09",
    adults: int = 1,
    children: int = 0,
    infants: int = 0,
    seat_class: str = "Y",
    raw_json: bool = False,
) -> str:
    """
    Search for international flights using the specified parameters.

    Args:
        trip_type: Trip type (RT for Round Trip, OW for One Way).
        departure_city: IATA code for the departure city (e.g., ICN).
        arrival_city: IATA code for the arrival city (e.g., FUK).
        departure_date: Departure date in YYYY-MM-DD format.
        return_date: Return date in YYYY-MM-DD format (required for RT).
        adults: Number of adults.
        children: Number of children.
        infants: Number of infants.
        seat_class: Seat class (Y: Economy, P: Premium, C: Business, F: First).
        raw_json: If True, returns the raw JSON response instead of a summary.
    """
    
    # Remove hyphens from dates as the API seems to expect YYYYMMDD based on the sample
    s_dt = departure_date.replace("-", "")
    e_dt = return_date.replace("-", "") if return_date else ""

    # Construct the API endpoint
    endpoint = "/flight/api/international/booking/flightInterFareSearchJson"
    
    # Use a real current timestamp
    timestamp = str(int(time.time() * 1000))

    params = {
        "skin": "onlinetour",
        "resId": "",
        "soto": "N",
        "trip": trip_type,
        "startDt": s_dt,
        "endDt": e_dt,
        "sDate1": "",
        "sDate2": "",
        "sDate3": "",
        "sCity1": departure_city,
        "eCity1": arrival_city,
        "eCity1NtDesc": "",
        "sCity2": arrival_city if trip_type == "RT" else "",
        "eCity2": departure_city if trip_type == "RT" else "",
        "sCity3": "",
        "eCity3": "",
        "adt": adults,
        "chd": children,
        "inf": infants,
        "filterAirLine": "",
        "filterViaNo": "",
        "seatType": seat_class,
        "best": "Y",
        "sgc": "",
        "rgc": "",
        "partnerCode": "",
        "eventNum": "",
        "classJoinNum": "",
        "partnerNum": "",
        "fareType": "Y",
        "eventInd": "",
        "splitNo": "1000",
        "epricingYn": "N",
        "blockGoodsYn": "Y",
        "summary": "N",
        "schedule": "Y",
        "SGMap": "Y",
        "Host": "Y",
        "passDataYn": "N",
        "_": timestamp
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.onlinetour.co.kr/flight/international",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "X-Requested-With": "XMLHttpRequest"
    }

    url = f"{BASE_URL.rstrip('/')}{endpoint}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            try:
                data = response.json()
            except json.JSONDecodeError:
                content_prefix = response.text[:200]
                return f"Error: API returned non-JSON response. Content start: {content_prefix}"
            
            if raw_json:
                return json.dumps(data, indent=2, ensure_ascii=False)

            # Check for errors in the response
            summary_info = data.get("GoodsSummary", {})
            if summary_info.get("errCnt") != "OK":
                return f"API Error: {summary_info.get('errMsg', 'Unknown error')}"

            goods = data.get("GoodsList", {}).get("Goods", [])
            if not goods:
                return "No flights found for the given criteria."

            # Format the results into a readable summary
            results = []
            results.append(f"Found {len(goods)} flight offers.")
            results.append("-" * 50)

            for i, item in enumerate(goods[:10]): # Limit to top 10 for readability
                airline = item.get("AirLineKor", "Unknown Airline")
                start_routine = item.get("StartRoutine", "")
                return_routine = item.get("ReturnRoutine", "")
                
                # Basic fare info
                sale_fare = item.get("SaleFare", 0)
                tax = item.get("Tax", 0)
                q_charge = item.get("Qcharge", 0)
                total_base_fare = sale_fare + tax + q_charge
                
                # Check for event fares (card discounts)
                event_fares = item.get("EventFareList", {}).get("EventFare", [])
                cheapest_event = ""
                if event_fares:
                    # Often the first one is the best or they are sorted
                    best_event = event_fares[0]
                    best_total = best_event.get("TotalSaleFare", total_base_fare)
                    cheapest_event = f" (Card Discount: {best_total:,} KRW - {best_event.get('FareTypeDesc')})"

                baggage = item.get("AdultBagInfo", "N/A")
                
                res = [
                    f"[{i+1}] {airline}",
                    f"   Route: {start_routine} / {return_routine}",
                    f"   Price: {total_base_fare:,} KRW{cheapest_event}",
                    f"   Baggage: {baggage}",
                    f"   Fare Type: {item.get('FareTypeDesc', '')} ({item.get('FareFix', '')})",
                ]
                results.append("\n".join(res))
                results.append("-" * 30)

            if len(goods) > 10:
                results.append(f"... and {len(goods) - 10} more results.")

            return "\n".join(results)
            
    except httpx.HTTPError as e:
        return f"Error fetching flight data: {str(e)}"
    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

if __name__ == "__main__":
    logger.info(f"🚀 MCP server started on port {os.getenv('PORT', 8080)}")
    # Could also use 'sse' transport, host="0.0.0.0" required for Cloud Run.
    port = int(os.getenv("PORT", 8080))
    asyncio.run(
        mcp.run_sse_async(
            transport="streamable-http",
            host="0.0.0.0",
            port=port,
        )
    )
