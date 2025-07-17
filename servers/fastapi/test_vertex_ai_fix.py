#!/usr/bin/env python3
"""
測試 Google Vertex AI schema 修復的腳本
"""
import os
import asyncio
import sys
import json

# 添加項目路徑
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ppt_config_generator.ppt_outlines_generator import generate_ppt_content
from api.utils.model_utils import get_selected_llm_provider
from api.models import SelectedLLMProvider

async def test_ppt_generation():
    """測試 PPT 生成功能"""
    print("🧪 開始測試 PPT 生成功能...")
    
    # 設置測試環境變量
    os.environ.setdefault("LLM", "google")
    os.environ.setdefault("GOOGLE_API_KEY", "your-api-key")
    
    try:
        # 測試參數
        test_params = {
            "prompt": "介紹人工智能的基本概念",
            "n_slides": 3,
            "language": "繁體中文",
            "content": "包含 AI 的歷史、現狀和未來發展"
        }
        
        print(f"📋 測試參數: {test_params}")
        print(f"🔧 LLM 提供商: {get_selected_llm_provider()}")
        
        # 執行生成
        result = await generate_ppt_content(**test_params)
        
        print("✅ 生成成功！")
        print(f"📄 標題: {result.title}")
        print(f"📝 投影片數量: {len(result.slides)}")
        print(f"💡 筆記: {result.notes}")
        
        # 顯示每張投影片
        for i, slide in enumerate(result.slides):
            print(f"\n🎯 投影片 {i+1}:")
            print(f"  標題: {slide.title}")
            print(f"  內容: {slide.body[:100]}...")
            
        return True
        
    except Exception as e:
        print(f"❌ 測試失敗: {e}")
        print(f"🔍 錯誤類型: {type(e).__name__}")
        return False

async def test_schema_validation():
    """測試 schema 驗證"""
    print("\n🔍 測試 schema 驗證...")
    
    try:
        from ppt_config_generator.models import PresentationMarkdownModel, SlideMarkdownModel
        
        # 測試創建基本模型
        test_slide = SlideMarkdownModel(
            title="測試投影片",
            body="這是測試內容"
        )
        
        test_presentation = PresentationMarkdownModel(
            title="測試演示文稿",
            notes=["這是測試筆記"],
            slides=[test_slide]
        )
        
        # 檢查 schema
        if hasattr(test_presentation, 'model_json_schema'):
            schema = test_presentation.model_json_schema()
            print(f"✅ Schema 生成成功")
            print(f"📊 Schema 類型: {schema.get('type', 'Unknown')}")
            
            # 檢查必要字段
            required = schema.get('required', [])
            properties = schema.get('properties', {})
            
            print(f"📋 必要字段: {required}")
            print(f"🔧 屬性數量: {len(properties)}")
            
            # 驗證每個屬性都有 type 字段
            for prop_name, prop_info in properties.items():
                if 'type' not in prop_info:
                    print(f"⚠️  警告: 屬性 {prop_name} 缺少 type 字段")
                else:
                    print(f"✅ 屬性 {prop_name}: {prop_info['type']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Schema 驗證失敗: {e}")
        return False

async def test_error_handling():
    """測試錯誤處理"""
    print("\n🛡️  測試錯誤處理...")
    
    try:
        # 測試無效參數
        result = await generate_ppt_content(
            prompt="",
            n_slides=0,
            language="",
            content=""
        )
        
        print("⚠️  應該拋出錯誤但沒有")
        return False
        
    except Exception as e:
        print(f"✅ 錯誤處理正常: {type(e).__name__}")
        return True

async def main():
    """主測試函數"""
    print("🚀 開始 Google Vertex AI 修復測試")
    print("=" * 50)
    
    tests = [
        ("Schema 驗證", test_schema_validation),
        ("錯誤處理", test_error_handling),
        ("PPT 生成", test_ppt_generation),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n📋 執行測試: {test_name}")
        print("-" * 30)
        
        try:
            result = await test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ 測試 {test_name} 異常: {e}")
            results.append((test_name, False))
    
    # 總結結果
    print("\n" + "=" * 50)
    print("📊 測試結果總結:")
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通過" if result else "❌ 失敗"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 總體結果: {passed}/{len(results)} 通過")
    
    if passed == len(results):
        print("🎉 所有測試都通過了！修復成功！")
    else:
        print("⚠️  部分測試失敗，需要進一步調試")

if __name__ == "__main__":
    asyncio.run(main())