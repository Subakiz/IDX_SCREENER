import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pandas as pd
import sqlite3
import time
import logging

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DASHBOARD")

def run_dashboard_server():
    app = dash.Dash(__name__)

    app.layout = html.Div([
        html.H1("IDX Hybrid Trading System"),
        html.Div([
            dcc.Graph(id='live-price-chart'),
            dcc.Interval(
                id='interval-component',
                interval=1000, # Update every second
                n_intervals=0
            )
        ])
    ])

    @app.callback(
        Output('live-price-chart', 'figure'),
        [Input('interval-component', 'n_intervals')]
    )
    def update_graph_live(n):
        # Connect to SQLite DB (Shared with Trading Process)
        try:
            conn = sqlite3.connect('market_data.db')
            # Query recent ticks
            df = pd.read_sql_query("SELECT * FROM ticks ORDER BY timestamp DESC LIMIT 200", conn)
            conn.close()

            if df.empty:
                return go.Figure()

            # Process Data
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = df.sort_values('timestamp')

            # Create Plot
            fig = go.Figure()

            # Price Line
            fig.add_trace(go.Scatter(
                x=df['timestamp'],
                y=df['price'],
                mode='lines+markers',
                name='Price'
            ))

            # Layout updates
            fig.update_layout(
                title=f"Live Market Data: {df['symbol'].iloc[0] if not df.empty else 'N/A'}",
                xaxis_title="Time",
                yaxis_title="Price (IDR)",
                template="plotly_dark"
            )

            return fig

        except Exception as e:
            logger.error(f"Dashboard Error: {e}")
            return go.Figure()

    logger.info("Starting Dashboard Server...")
    app.run(debug=False, host='0.0.0.0', port=8050)

if __name__ == "__main__":
    run_dashboard_server()
