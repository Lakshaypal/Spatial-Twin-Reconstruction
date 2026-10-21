Shader "Custom/VertexColor" {
    Properties {
        _Color ("Main Color", Color) = (1,1,1,1)
    }
    SubShader {
        Tags { "RenderType"="Opaque" }
        LOD 200

        CGPROGRAM
        #pragma surface surf Lambert vertex:vert

        struct Input {
            float4 vertColor;
        };

        fixed4 _Color;

        void vert(inout appdata_full v, out Input o) {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            o.vertColor = v.color;
        }

        void surf(Input IN, inout SurfaceOutput o) {
            o.Albedo = IN.vertColor.rgb * _Color.rgb;
            o.Alpha = IN.vertColor.a * _Color.a;
        }
        ENDCG
    }
    FallBack "Diffuse"
}
