import json
import math
import requests

from datetime import datetime
from pathlib import Path
from collections import defaultdict


# ============================================================
# CONFIG
# ============================================================

BASE_DIR = (
    Path(__file__).resolve().parent.parent
)

DATA_FILE = (
    BASE_DIR
    / "data"
    / "ndx_options.json"
)

OUTPUT_FILE = (
    BASE_DIR
    / "output"
    / "gex_levels.json"
)

NQ_SYMBOL = "NQ=F"

CONTRACT_MULTIPLIER = 100

RISK_FREE_RATE = 0.04
DIVIDEND_YIELD = 0.00

SCAN_PERCENT = 0.15
SCAN_STEP = 5.0

MIN_OPEN_INTEREST = 1

TOP_LEVELS = 10


# ============================================================
# NORMAL DISTRIBUTION
# ============================================================

def normal_pdf(x):

    return (
        math.exp(
            -0.5 * x * x
        )
        / math.sqrt(
            2.0 * math.pi
        )
    )


# ============================================================
# BLACK-SCHOLES GAMMA
# ============================================================

def black_scholes_gamma(
    spot,
    strike,
    time_to_expiry,
    volatility
):

    if spot <= 0:
        return 0.0

    if strike <= 0:
        return 0.0

    if time_to_expiry <= 0:
        return 0.0

    if volatility <= 0:
        return 0.0

    try:

        d1 = (
            math.log(
                spot / strike
            )
            + (
                RISK_FREE_RATE
                - DIVIDEND_YIELD
                + 0.5
                * volatility
                * volatility
            )
            * time_to_expiry
        ) / (
            volatility
            * math.sqrt(
                time_to_expiry
            )
        )

        gamma = (
            math.exp(
                -DIVIDEND_YIELD
                * time_to_expiry
            )
            * normal_pdf(d1)
            / (
                spot
                * volatility
                * math.sqrt(
                    time_to_expiry
                )
            )
        )

        return gamma

    except Exception:

        return 0.0


# ============================================================
# NDX -> NQ
# ============================================================

def ndx_to_nq(
    ndx_price,
    basis
):

    if ndx_price is None:
        return None

    return (
        ndx_price
        + basis
    )


# ============================================================
# GET NQ PRICE
# ============================================================

def get_nq_price():

    print(
        "Getting NQ futures price..."
    )

    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        "NQ=F"
        "?range=1d&interval=1m"
    )

    headers = {
        "User-Agent":
            "Mozilla/5.0"
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20
    )

    response.raise_for_status()

    data = response.json()

    result = (
        data["chart"]
        ["result"][0]
    )

    meta = result["meta"]

    price = (
        meta.get(
            "regularMarketPrice"
        )
        or
        meta.get(
            "previousClose"
        )
    )

    if price is None:

        raise RuntimeError(
            "Could not obtain NQ futures price."
        )

    return float(price)


# ============================================================
# LOAD DATA
# ============================================================

def load_data():

    print(
        "Loading NDX options data..."
    )

    if not DATA_FILE.exists():

        raise FileNotFoundError(
            f"Could not find:\n{DATA_FILE}"
        )

    with open(
        DATA_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        raw = json.load(f)

    return raw


# ============================================================
# GET OPTIONS
# ============================================================

def get_options(raw):

    return (
        raw
        ["data"]
        ["data"]
        ["options"]
    )


# ============================================================
# GET MARKET DATA
# ============================================================

def get_market_data(raw):

    return (
        raw
        ["data"]
        ["data"]
    )


# ============================================================
# PARSE CBOE SYMBOL
# ============================================================

def parse_option_symbol(symbol):

    if not symbol:
        return None

    symbol = str(symbol)

    # --------------------------------------------------------
    # Standard format:
    #
    # NDX260918C04000000
    #
    # NDX
    # YYMMDD
    # C/P
    # STRIKE * 1000
    # --------------------------------------------------------

    if len(symbol) >= 18:

        try:

            expiration_text = (
                symbol[3:9]
            )

            option_type = (
                symbol[9]
            )

            strike_text = (
                symbol[10:]
            )

            expiration = (
                datetime.strptime(
                    expiration_text,
                    "%y%m%d"
                ).date()
            )

            strike = (
                int(strike_text)
                / 1000.0
            )

            if option_type not in (
                "C",
                "P"
            ):

                return None

            return {
                "expiration":
                    expiration,

                "type":
                    option_type,

                "strike":
                    strike
            }

        except Exception:

            return None

    return None


# ============================================================
# GET MARKET DATE
# ============================================================

def get_market_date(
    options
):

    dates = []

    for option in options:

        trade_time = (
            option.get(
                "last_trade_time"
            )
        )

        if not trade_time:
            continue

        try:

            parsed = datetime.fromisoformat(
                trade_time
            )

            dates.append(
                parsed.date()
            )

        except Exception:

            continue

    if not dates:

        raise RuntimeError(
            "Could not determine market date."
        )

    return max(dates)


# ============================================================
# GET IV
# ============================================================

def get_iv(
    option
):

    value = option.get(
        "iv"
    )

    if value is None:
        return None

    try:

        value = float(value)

    except Exception:

        return None

    if value <= 0:
        return None

    # Cboe data can sometimes expose
    # volatility as a percentage.
    if value > 3:

        value /= 100.0

    if value <= 0:
        return None

    return value


# ============================================================
# GET OPEN INTEREST
# ============================================================

def get_open_interest(
    option
):

    value = option.get(
        "open_interest",
        0
    )

    try:

        return float(value)

    except Exception:

        return 0.0


# ============================================================
# PREPARE OPTIONS
# ============================================================

def prepare_options(
    options,
    market_date
):

    prepared = []

    for option in options:

        symbol = option.get(
            "option"
        )

        parsed = parse_option_symbol(
            symbol
        )

        if parsed is None:
            continue

        expiration = (
            parsed["expiration"]
        )

        if expiration < market_date:

            continue

        strike = (
            parsed["strike"]
        )

        option_type = (
            parsed["type"]
        )

        oi = get_open_interest(
            option
        )

        if oi < MIN_OPEN_INTEREST:

            continue

        iv = get_iv(
            option
        )

        # ----------------------------------------------------
        # Cboe sometimes reports IV as 0.
        #
        # For those contracts we cannot calculate
        # Black-Scholes gamma reliably, so exclude them.
        # ----------------------------------------------------

        if iv is None:

            continue

        prepared.append(
            {
                "symbol":
                    symbol,

                "expiration":
                    expiration,

                "type":
                    option_type,

                "strike":
                    strike,

                "oi":
                    oi,

                "iv":
                    iv
            }
        )

    return prepared


# ============================================================
# TIME TO EXPIRATION
# ============================================================

def time_to_expiration(
    market_date,
    expiration
):

    days = (
        expiration
        - market_date
    ).days

    if days <= 0:

        return 0.0

    return (
        days / 365.0
    )


# ============================================================
# OPTION GEX
# ============================================================

def calculate_option_gex(
    option,
    hypothetical_spot,
    market_date
):

    t = time_to_expiration(
        market_date,
        option["expiration"]
    )

    if t <= 0:

        return 0.0

    gamma = black_scholes_gamma(
        hypothetical_spot,
        option["strike"],
        t,
        option["iv"]
    )

    if gamma <= 0:

        return 0.0

    gex = (
        gamma
        * option["oi"]
        * CONTRACT_MULTIPLIER
        * hypothetical_spot
        * hypothetical_spot
        * 0.01
    )

    if option["type"] == "P":

        gex *= -1

    return gex


# ============================================================
# TOTAL GEX
# ============================================================

def calculate_total_gex(
    options,
    hypothetical_spot,
    market_date
):

    total = 0.0

    for option in options:

        total += (
            calculate_option_gex(
                option,
                hypothetical_spot,
                market_date
            )
        )

    return total


# ============================================================
# GEX BY STRIKE
# ============================================================

def calculate_gex_by_strike(
    options,
    hypothetical_spot,
    market_date
):

    levels = defaultdict(float)

    for option in options:

        gex = (
            calculate_option_gex(
                option,
                hypothetical_spot,
                market_date
            )
        )

        levels[
            option["strike"]
        ] += gex

    return dict(levels)


# ============================================================
# BUILD GEX CURVE
# ============================================================

def build_gex_curve(
    options,
    spot,
    market_date
):

    lower = (
        spot
        * (
            1.0
            - SCAN_PERCENT
        )
    )

    upper = (
        spot
        * (
            1.0
            + SCAN_PERCENT
        )
    )

    curve = []

    price = lower

    while price <= upper:

        gex = (
            calculate_total_gex(
                options,
                price,
                market_date
            )
        )

        curve.append(
            (
                price,
                gex
            )
        )

        price += SCAN_STEP

    return curve


# ============================================================
# FIND GAMMA FLIP
# ============================================================

def find_gamma_flip(
    curve
):

    previous_price = None
    previous_gex = None

    for price, gex in curve:

        if previous_price is not None:

            if gex == 0:

                return price

            crossed = (

                (
                    previous_gex < 0
                    and gex > 0
                )

                or

                (
                    previous_gex > 0
                    and gex < 0
                )
            )

            if crossed:

                difference = (
                    gex
                    - previous_gex
                )

                if difference == 0:

                    return price

                fraction = (
                    -previous_gex
                    / difference
                )

                return (
                    previous_price
                    + (
                        price
                        - previous_price
                    )
                    * fraction
                )

        previous_price = price
        previous_gex = gex

    return None


# ============================================================
# FIND WALLS
# ============================================================

def find_walls(
    gex_by_strike
):

    positive = [
        (
            strike,
            value
        )

        for strike, value
        in gex_by_strike.items()

        if value > 0
    ]

    negative = [
        (
            strike,
            value
        )

        for strike, value
        in gex_by_strike.items()

        if value < 0
    ]

    call_wall = None
    put_wall = None

    if positive:

        call_wall = max(
            positive,
            key=lambda x: x[1]
        )[0]

    if negative:

        put_wall = min(
            negative,
            key=lambda x: x[1]
        )[0]

    return (
        call_wall,
        put_wall
    )


# ============================================================
# MAX PAIN
# ============================================================

def calculate_max_pain(
    options,
    expiration
):

    expiry_options = [

        option

        for option
        in options

        if option["expiration"]
        == expiration
    ]

    if not expiry_options:

        return None

    strikes = sorted(
        set(
            option["strike"]
            for option
            in expiry_options
        )
    )

    best_strike = None
    lowest_pain = None

    for settlement in strikes:

        pain = 0.0

        for option in expiry_options:

            strike = option[
                "strike"
            ]

            oi = option[
                "oi"
            ]

            if option["type"] == "C":

                intrinsic = max(
                    settlement
                    - strike,
                    0
                )

            else:

                intrinsic = max(
                    strike
                    - settlement,
                    0
                )

            pain += (
                intrinsic
                * oi
            )

        if (
            lowest_pain is None
            or pain < lowest_pain
        ):

            lowest_pain = pain
            best_strike = settlement

    return best_strike


# ============================================================
# MAJOR LEVELS
# ============================================================

def get_positive_levels(
    gex_by_strike
):

    levels = [

        (
            strike,
            value
        )

        for strike, value
        in gex_by_strike.items()

        if value > 0
    ]

    levels.sort(
        key=lambda x: x[1],
        reverse=True
    )

    return levels[
        :TOP_LEVELS
    ]


def get_negative_levels(
    gex_by_strike
):

    levels = [

        (
            strike,
            value
        )

        for strike, value
        in gex_by_strike.items()

        if value < 0
    ]

    levels.sort(
        key=lambda x: x[1]
    )

    return levels[
        :TOP_LEVELS
    ]


# ============================================================
# SAVE JSON
# ============================================================

def save_output(
    snapshot_date,
    ndx_spot,
    nq_price,
    basis,

    full_gamma_flip,
    call_wall,
    put_wall,
    max_pain,

    zero_dte_expiration,
    zero_dte_gamma_flip,
    zero_dte_call_wall,
    zero_dte_put_wall,

    positive_levels,
    negative_levels,

    zero_positive,
    zero_negative
):

    output = {

        "updated_at":
            datetime.now().isoformat(),

        "market_data_date":
            str(snapshot_date),

        "ndx_spot":
            round(
                ndx_spot,
                2
            ),

        "nq_price":
            round(
                nq_price,
                2
            ),

        "ndx_nq_basis":
            round(
                basis,
                2
            ),

        "full_chain": {

            "gamma_flip_ndx":
                (
                    round(
                        full_gamma_flip,
                        2
                    )
                    if full_gamma_flip
                    is not None
                    else None
                ),

            "gamma_flip_nq":
                (
                    round(
                        ndx_to_nq(
                            full_gamma_flip,
                            basis
                        ),
                        2
                    )
                    if full_gamma_flip
                    is not None
                    else None
                ),

            "call_wall_ndx":
                (
                    round(
                        call_wall,
                        2
                    )
                    if call_wall
                    is not None
                    else None
                ),

            "call_wall_nq":
                (
                    round(
                        ndx_to_nq(
                            call_wall,
                            basis
                        ),
                        2
                    )
                    if call_wall
                    is not None
                    else None
                ),

            "put_wall_ndx":
                (
                    round(
                        put_wall,
                        2
                    )
                    if put_wall
                    is not None
                    else None
                ),

            "put_wall_nq":
                (
                    round(
                        ndx_to_nq(
                            put_wall,
                            basis
                        ),
                        2
                    )
                    if put_wall
                    is not None
                    else None
                ),

            "max_pain_ndx":
                (
                    round(
                        max_pain,
                        2
                    )
                    if max_pain
                    is not None
                    else None
                ),

            "max_pain_nq":
                (
                    round(
                        ndx_to_nq(
                            max_pain,
                            basis
                        ),
                        2
                    )
                    if max_pain
                    is not None
                    else None
                )
        },

        "zero_dte": {

            "expiration":
                (
                    str(zero_dte_expiration)
                    if zero_dte_expiration is not None
                    else None
                ),

            "gamma_flip_ndx":
                (
                    round(
                        zero_dte_gamma_flip,
                        2
                    )
                    if zero_dte_gamma_flip
                    is not None
                    else None
                ),

            "gamma_flip_nq":
                (
                    round(
                        ndx_to_nq(
                            zero_dte_gamma_flip,
                            basis
                        ),
                        2
                    )
                    if zero_dte_gamma_flip
                    is not None
                    else None
                ),

            "call_wall_ndx":
                (
                    round(
                        zero_dte_call_wall,
                        2
                    )
                    if zero_dte_call_wall
                    is not None
                    else None
                ),

            "call_wall_nq":
                (
                    round(
                        ndx_to_nq(
                            zero_dte_call_wall,
                            basis
                        ),
                        2
                    )
                    if zero_dte_call_wall
                    is not None
                    else None
                ),

            "put_wall_ndx":
                (
                    round(
                        zero_dte_put_wall,
                        2
                    )
                    if zero_dte_put_wall
                    is not None
                    else None
                ),

            "put_wall_nq":
                (
                    round(
                        ndx_to_nq(
                            zero_dte_put_wall,
                            basis
                        ),
                        2
                    )
                    if zero_dte_put_wall
                    is not None
                    else None
                )
        },

        "major_positive_gamma": [

            {
                "ndx":
                    round(
                        strike,
                        2
                    ),

                "nq":
                    round(
                        ndx_to_nq(
                            strike,
                            basis
                        ),
                        2
                    ),

                "gex":
                    round(
                        value
                    )
            }

            for strike, value
            in positive_levels
        ],

        "major_negative_gamma": [

            {
                "ndx":
                    round(
                        strike,
                        2
                    ),

                "nq":
                    round(
                        ndx_to_nq(
                            strike,
                            basis
                        ),
                        2
                    ),

                "gex":
                    round(
                        value
                    )
            }

            for strike, value
            in negative_levels
        ],

        "zero_dte_major_positive_gamma": [

            {
                "ndx":
                    round(
                        strike,
                        2
                    ),

                "nq":
                    round(
                        ndx_to_nq(
                            strike,
                            basis
                        ),
                        2
                    ),

                "gex":
                    round(
                        value
                    )
            }

            for strike, value
            in zero_positive
        ],

        "zero_dte_major_negative_gamma": [

            {
                "ndx":
                    round(
                        strike,
                        2
                    ),

                "nq":
                    round(
                        ndx_to_nq(
                            strike,
                            basis
                        ),
                        2
                    ),

                "gex":
                    round(
                        value
                    )
            }

            for strike, value
            in zero_negative
        ]
    }

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            output,
            f,
            indent=2
        )

    print()
    print(
        "TRADINGVIEW OUTPUT"
    )
    print(
        "----------------------------------------"
    )
    print(
        "Saved to:"
    )
    print(
        OUTPUT_FILE
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print(
        "========================================"
    )
    print(
        "       NDX GEX ENGINE - STAGE 3"
    )
    print(
        "========================================"
    )
    print()

    # --------------------------------------------------------
    # LOAD
    # --------------------------------------------------------

    raw = load_data()

    options = get_options(
        raw
    )

    market_data = get_market_data(
        raw
    )

    ndx_spot = float(
        market_data[
            "current_price"
        ]
    )

    nq_price = get_nq_price()

    basis = (
        nq_price
        - ndx_spot
    )

    market_date = get_market_date(
        options
    )

    print()
    print(
        "MARKET DATA DATE:",
        market_date
    )

    print(
        "NDX SPOT:",
        ndx_spot
    )

    print(
        "NQ PRICE:",
        nq_price
    )

    print(
        "NQ/NDX BASIS:",
        round(
            basis,
            2
        )
    )

    print(
        "TOTAL RAW OPTIONS:",
        len(options)
    )

    # --------------------------------------------------------
    # PREPARE
    # --------------------------------------------------------

    prepared = prepare_options(
        options,
        market_date
    )

    print()
    print(
        "OPTIONS PARSED:",
        len(options)
    )

    print(
        "OPTIONS USED:",
        len(prepared)
    )

    if not prepared:

        raise RuntimeError(
            "No usable options were found."
        )

    # --------------------------------------------------------
    # EXPIRATIONS
    # --------------------------------------------------------

    expiration_counts = (
        defaultdict(int)
    )

    for option in prepared:

        expiration_counts[
            option["expiration"]
        ] += 1

    print()
    print(
        "EXPIRATION BREAKDOWN"
    )
    print(
        "----------------------------------------"
    )

    for expiration in sorted(
        expiration_counts
    ):

        print(
            expiration,
            ":",
            expiration_counts[
                expiration
            ]
        )

    # --------------------------------------------------------
    # NEXT EXPIRATION
    # --------------------------------------------------------

    future_expirations = sorted(

        expiration

        for expiration
        in expiration_counts

        if expiration >= market_date
    )

    if not future_expirations:

        raise RuntimeError(
            "No option expirations were found."
        )

    next_expiration = (
        future_expirations[0]
    )

    # True 0DTE means the option expires on the market-data date.
    # The next future expiry is NOT 0DTE.
    zero_dte_expiration = (
        market_date
        if market_date in expiration_counts
        else None
    )

    print()
    print(
        "NEXT EXPIRATION:",
        next_expiration
    )

    # --------------------------------------------------------
    # FULL GEX
    # --------------------------------------------------------

    current_gex = (
        calculate_total_gex(
            prepared,
            ndx_spot,
            market_date
        )
    )

    print()
    print(
        "CURRENT TOTAL GEX:",
        f"{current_gex:,.0f}"
    )

    print(
        "BUILDING FULL GEX CURVE..."
    )

    full_curve = (
        build_gex_curve(
            prepared,
            ndx_spot,
            market_date
        )
    )

    print(
        "GEX AT CURRENT PRICE:",
        f"{current_gex:,.0f}"
    )

    full_gamma_flip = (
        find_gamma_flip(
            full_curve
        )
    )

    full_gex_by_strike = (
        calculate_gex_by_strike(
            prepared,
            ndx_spot,
            market_date
        )
    )

    call_wall, put_wall = (
        find_walls(
            full_gex_by_strike
        )
    )

    max_pain = (
        calculate_max_pain(
            prepared,
            next_expiration
        )
    )

    positive_levels = (
        get_positive_levels(
            full_gex_by_strike
        )
    )

    negative_levels = (
        get_negative_levels(
            full_gex_by_strike
        )
    )

    # --------------------------------------------------------
    # FULL CHAIN DISPLAY
    # --------------------------------------------------------

    print()
    print(
        "FULL CHAIN"
    )
    print(
        "----------------------------------------"
    )

    if full_gamma_flip is not None:

        print(
            "GAMMA FLIP:",
            f"NDX {full_gamma_flip:.2f}",
            "-> NQ",
            f"{ndx_to_nq(full_gamma_flip, basis):.2f}"
        )

    else:

        print(
            "GAMMA FLIP: None"
        )

    if call_wall is not None:

        print(
            "CALL WALL:",
            f"NDX {call_wall:.2f}",
            "-> NQ",
            f"{ndx_to_nq(call_wall, basis):.2f}"
        )

    else:

        print(
            "CALL WALL: None"
        )

    if put_wall is not None:

        print(
            "PUT WALL:",
            f"NDX {put_wall:.2f}",
            "-> NQ",
            f"{ndx_to_nq(put_wall, basis):.2f}"
        )

    else:

        print(
            "PUT WALL: None"
        )

    if max_pain is not None:

        print(
            "MAX PAIN:",
            f"NDX {max_pain:.2f}",
            "-> NQ",
            f"{ndx_to_nq(max_pain, basis):.2f}"
        )

    else:

        print(
            "MAX PAIN: None"
        )

    # --------------------------------------------------------
    # 0DTE
    # --------------------------------------------------------

    print()
    print(
        "0DTE"
    )
    print(
        "----------------------------------------"
    )

    if zero_dte_expiration is None:

        zero_dte_options = []
        zero_dte_gamma_flip = None
        zero_dte_call_wall = None
        zero_dte_put_wall = None
        zero_positive = []
        zero_negative = []

        print(
            "0DTE EXPIRATION: None"
        )
        print(
            "0DTE OPTIONS USED: 0"
        )
        print(
            "No options expire on the market-data date."
        )

    else:

        zero_dte_options = [

            option

            for option
            in prepared

            if option["expiration"]
            == zero_dte_expiration
        ]

        print(
            "0DTE EXPIRATION:",
            zero_dte_expiration
        )

        print(
            "0DTE OPTIONS USED:",
            len(zero_dte_options)
        )

        zero_dte_current_gex = (
            calculate_total_gex(
                zero_dte_options,
                ndx_spot,
                market_date
            )
        )

        print(
            "0DTE CURRENT GEX:",
            f"{zero_dte_current_gex:,.0f}"
        )

        print(
            "BUILDING 0DTE GEX CURVE..."
        )

        zero_dte_curve = (
            build_gex_curve(
                zero_dte_options,
                ndx_spot,
                market_date
            )
        )

        zero_dte_gamma_flip = (
            find_gamma_flip(
                zero_dte_curve
            )
        )

        zero_dte_gex_by_strike = (
            calculate_gex_by_strike(
                zero_dte_options,
                ndx_spot,
                market_date
            )
        )

        (
            zero_dte_call_wall,
            zero_dte_put_wall
        ) = find_walls(
            zero_dte_gex_by_strike
        )

        zero_positive = (
            get_positive_levels(
                zero_dte_gex_by_strike
            )
        )

        zero_negative = (
            get_negative_levels(
                zero_dte_gex_by_strike
            )
        )

        if zero_dte_gamma_flip is not None:

            print(
                "0DTE GAMMA FLIP:",
                f"NDX {zero_dte_gamma_flip:.2f}",
                "-> NQ",
                f"{ndx_to_nq(zero_dte_gamma_flip, basis):.2f}"
            )

        else:

            print(
                "0DTE GAMMA FLIP: None"
            )

        if zero_dte_call_wall is not None:

            print(
                "0DTE CALL WALL:",
                f"NDX {zero_dte_call_wall:.2f}",
                "-> NQ",
                f"{ndx_to_nq(zero_dte_call_wall, basis):.2f}"
            )

        else:

            print(
                "0DTE CALL WALL: None"
            )

        if zero_dte_put_wall is not None:

            print(
                "0DTE PUT WALL:",
                f"NDX {zero_dte_put_wall:.2f}",
                "-> NQ",
                f"{ndx_to_nq(zero_dte_put_wall, basis):.2f}"
            )

        else:

            print(
                "0DTE PUT WALL: None"
            )

    # --------------------------------------------------------
    # POSITIVE LEVELS
    # --------------------------------------------------------

    # --------------------------------------------------------
    # POSITIVE LEVELS
    # --------------------------------------------------------

    print()
    print(
        "MAJOR POSITIVE GAMMA"
    )
    print(
        "----------------------------------------"
    )

    for strike, value in positive_levels:

        print(
            f"{strike:<10.2f}",
            f"{value:>15,.0f}",
            "-> NQ",
            f"{ndx_to_nq(strike, basis):.2f}"
        )

    # --------------------------------------------------------
    # NEGATIVE LEVELS
    # --------------------------------------------------------

    print()
    print(
        "MAJOR NEGATIVE GAMMA"
    )
    print(
        "----------------------------------------"
    )

    for strike, value in negative_levels:

        print(
            f"{strike:<10.2f}",
            f"{value:>15,.0f}",
            "-> NQ",
            f"{ndx_to_nq(strike, basis):.2f}"
        )

    # --------------------------------------------------------
    # 0DTE POSITIVE
    # --------------------------------------------------------

    print()
    print(
        "0DTE MAJOR POSITIVE GAMMA"
    )
    print(
        "----------------------------------------"
    )

    for strike, value in zero_positive:

        print(
            f"{strike:<10.2f}",
            f"{value:>15,.0f}",
            "-> NQ",
            f"{ndx_to_nq(strike, basis):.2f}"
        )

    # --------------------------------------------------------
    # 0DTE NEGATIVE
    # --------------------------------------------------------

    print()
    print(
        "0DTE MAJOR NEGATIVE GAMMA"
    )
    print(
        "----------------------------------------"
    )

    for strike, value in zero_negative:

        print(
            f"{strike:<10.2f}",
            f"{value:>15,.0f}",
            "-> NQ",
            f"{ndx_to_nq(strike, basis):.2f}"
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    save_output(

        market_date,
        ndx_spot,
        nq_price,
        basis,

        full_gamma_flip,
        call_wall,
        put_wall,
        max_pain,

        zero_dte_expiration,
        zero_dte_gamma_flip,
        zero_dte_call_wall,
        zero_dte_put_wall,

        positive_levels,
        negative_levels,

        zero_positive,
        zero_negative
    )

    # --------------------------------------------------------
    # COMPLETE
    # --------------------------------------------------------

    print()
    print(
        "========================================"
    )
    print(
        "          STAGE 3 COMPLETE"
    )
    print(
        "========================================"
    )


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    main()