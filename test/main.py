import argparse
from publisher import run_publisher
from subscriber import run_subscriber
from stress_pub import run_stress_test
from latency_analyze import run_latency_analysis

def main():
    parser = argparse.ArgumentParser(description="MQTT System Tester")
    parser.add_argument("mode", choices=["publisher", "subscriber", "stress", "analyze"],
                        help="Mode to run the system in")
    args = parser.parse_args()

    if args.mode == "publisher":
        run_publisher()
    elif args.mode == "subscriber":
        run_subscriber()
    elif args.mode == "stress":
        run_stress_test()
    elif args.mode == "analyze":
        run_latency_analysis()

if __name__ == "__main__":
    main()
