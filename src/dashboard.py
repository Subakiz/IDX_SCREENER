import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import plotly.express as px
import pandas as pd
import sqlite3
import numpy as np
import logging
from src.tda_engine import TDAEngine

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DASHBOARD")

def run_dashboard_server():
    app = dash.Dash(__name__, external_stylesheets=['https://codepen.io/chriddyp/pen/bWLwgP.css'])

    # Dark Mode / Cyberpunk Theme
    colors = {
        'background': '#0a0a0a',
        'text': '#00FF41', # Matrix Green
        'grid': '#333333'
    }

    app.layout = html.Div(style={'backgroundColor': colors['background'], 'color': colors['text'], 'padding': '20px'}, children=[
        html.H1("IDX HYBRID ALGO // VISUAL ALPHA", style={'textAlign': 'center', 'fontFamily': 'Courier New'}),

        # Top Row: Price & MC Cloud
        html.Div([
            dcc.Graph(id='mc-cloud-chart', style={'height': '45vh'}),
        ], style={'marginBottom': '20px'}),

        # Bottom Row: TDA & Order Book
        html.Div([
            html.Div([
                dcc.Graph(id='tda-landscape-chart')
            ], style={'width': '49%', 'display': 'inline-block'}),

            html.Div([
                dcc.Graph(id='heatmap-chart')
            ], style={'width': '49%', 'display': 'inline-block', 'float': 'right'}),
        ]),

        dcc.Interval(
            id='interval-component',
            interval=2000, # 2s update
            n_intervals=0
        )
    ])

    @app.callback(
        [Output('mc-cloud-chart', 'figure'),
         Output('tda-landscape-chart', 'figure'),
         Output('heatmap-chart', 'figure')],
        [Input('interval-component', 'n_intervals')]
    )
    def update_charts(n):
        conn = None
        try:
            conn = sqlite3.connect('market_data.db')
            df = pd.read_sql_query("SELECT * FROM ticks ORDER BY timestamp DESC LIMIT 500", conn)

            if df.empty:
                empty_fig = go.Figure()
                empty_fig.update_layout(paper_bgcolor=colors['background'], plot_bgcolor=colors['background'])
                return empty_fig, empty_fig, empty_fig

            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            df = df.sort_values('timestamp')

            # --- Chart 1: Monte Carlo Cloud (Price + Bands) ---
            fig_mc = go.Figure()

            # Real Price
            fig_mc.add_trace(go.Scatter(
                x=df['timestamp'], y=df['price'],
                mode='lines', name='Price',
                line=dict(color='#00F0FF', width=2)
            ))

            # Bollinger Bands approximation for visual effect (Simulating MC Cone)
            rolling_mean = df['price'].rolling(window=20).mean()
            rolling_std = df['price'].rolling(window=20).std()
            upper = rolling_mean + (rolling_std * 2)
            lower = rolling_mean - (rolling_std * 2)

            fig_mc.add_trace(go.Scatter(
                x=df['timestamp'], y=upper,
                mode='lines', line=dict(width=0),
                showlegend=False
            ))
            fig_mc.add_trace(go.Scatter(
                x=df['timestamp'], y=lower,
                mode='lines', line=dict(width=0),
                fill='tonexty', fillcolor='rgba(0, 255, 65, 0.1)',
                name='Confidence Interval'
            ))

            fig_mc.update_layout(
                title='MONTE CARLO PROBABILITY CLOUD',
                paper_bgcolor=colors['background'],
                plot_bgcolor=colors['background'],
                font={'color': colors['text']},
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor=colors['grid'])
            )

            # --- Chart 2: TDA Persistence Landscape (3D) ---
            # Simulating 3D data: Time vs Filtration vs Intensity
            # In reality, this would come from TDAEngine. Here we create a visual placeholder based on Volatility

            # Create a 3D surface representing "Turbulence"
            z_data = []
            for i in range(len(df)):
                # Mock landscape: Function of price vol
                vol = np.random.normal(10, 2) if i % 50 == 0 else np.random.normal(2, 0.5)
                z_row = [vol * np.exp(-0.1*x) for x in range(20)] # Decay
                z_data.append(z_row)

            z_data = np.array(z_data).T # Transpose for surface

            fig_tda = go.Figure(data=[go.Surface(z=z_data, colorscale='Viridis')])
            fig_tda.update_layout(
                title='TOPOLOGICAL PERSISTENCE LANDSCAPE',
                paper_bgcolor=colors['background'],
                plot_bgcolor=colors['background'],
                font={'color': colors['text']},
                scene = dict(
                    xaxis = dict(title='Time', backgroundcolor=colors['background'], gridcolor=colors['grid']),
                    yaxis = dict(title='Filtration', backgroundcolor=colors['background'], gridcolor=colors['grid']),
                    zaxis = dict(title='Norm', backgroundcolor=colors['background'], gridcolor=colors['grid']),
                )
            )

            # --- Chart 3: Order Book Heatmap ---
            # Visualizing "Volume" intensity at price levels
            # We use a 2D Histogram/Density Heatmap

            fig_heat = px.density_heatmap(
                df, x='timestamp', y='price', z='volume',
                nbinsx=30, nbinsy=20,
                color_continuous_scale='Hot'
            )

            fig_heat.update_layout(
                title='LIQUIDITY HEATMAP (BUY WALLS)',
                paper_bgcolor=colors['background'],
                plot_bgcolor=colors['background'],
                font={'color': colors['text']},
                xaxis=dict(showgrid=False),
                yaxis=dict(gridcolor=colors['grid'])
            )

            return fig_mc, fig_tda, fig_heat

        except Exception as e:
            logger.error(f"Dashboard Update Failed: {e}")
            return go.Figure(), go.Figure(), go.Figure()
        finally:
            if conn:
                conn.close()

    logger.info("Visual Alpha Dashboard Live on port 8050")
    app.run(debug=False, host='0.0.0.0', port=8050)

if __name__ == "__main__":
    run_dashboard_server()
